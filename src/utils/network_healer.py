"""
Project Astra - Network Healer (Self-Healing Layer)
Connection health monitoring, DNS failover, exponential backoff retry,
and platform health checks.
"""

import asyncio
import random
from typing import Callable, List, Optional, Tuple

import httpx

from src.utils.logger import logger
from src.utils.warp_manager import WarpManager


class NetworkHealer:
    """
    Layer 1-4 network self-healing system.
    - Ping endpoints for latency
    - DNS failover on NXDOMAIN
    - Exponential backoff for API calls
    - Platform health checks before operations
    """

    PING_ENDPOINTS: List[str] = [
        "https://www.google.com",
        "https://www.cloudflare.com",
        "https://github.com",
    ]
    LATENCY_THRESHOLD_MS: float = 500.0
    BACKOFF_BASE_SECONDS: float = 2.0
    MAX_RETRIES: int = 5

    def __init__(self, warp: Optional[WarpManager] = None) -> None:
        self.warp = warp or WarpManager()
        self.dns_servers: List[str] = ["8.8.8.8", "1.1.1.1"]

    async def health_check(self) -> Tuple[bool, List[str]]:
        """
        Layer 1: Ping 3 endpoints. If any fail or exceed latency threshold,
        trigger WARP reconnection.
        Returns (healthy, list_of_issues).
        """
        issues: List[str] = []
        total_latency = 0.0
        reachable_count = 0

        for endpoint in self.PING_ENDPOINTS:
            try:
                start = asyncio.get_event_loop().time()
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(endpoint)
                latency = (asyncio.get_event_loop().time() - start) * 1000
                total_latency += latency

                if response.status_code >= 400:
                    issues.append(f"{endpoint} returned HTTP {response.status_code}")
                elif latency > self.LATENCY_THRESHOLD_MS:
                    issues.append(f"{endpoint} latency {latency:.0f}ms exceeds threshold")
                else:
                    reachable_count += 1

            except httpx.TimeoutException:
                issues.append(f"{endpoint} timed out")
            except httpx.ConnectError as exc:
                issues.append(f"{endpoint} connection error: {exc}")
            except Exception as exc:
                issues.append(f"{endpoint} unexpected error: {exc}")

        healthy = reachable_count >= 2  # At least 2/3 must be healthy
        if not healthy:
            logger.warning(f"Network health check failed: {issues}")
        else:
            avg_latency = total_latency / max(reachable_count, 1)
            logger.debug(f"Network health OK. Avg latency: {avg_latency:.0f}ms")

        return healthy, issues

    async def heal_if_needed(self) -> bool:
        """
        If network is unhealthy, attempt to heal by reconnecting WARP.
        Returns True if network is now healthy.
        """
        healthy, issues = await self.health_check()
        if healthy:
            return True

        logger.info("Initiating network self-healing: reconnecting WARP...")
        try:
            await self.warp.rotate_ip()
            # Re-check after healing
            healthy, _ = await self.health_check()
            if healthy:
                logger.info("Network self-healing succeeded.")
            else:
                logger.error("Network self-healing failed. Network still unhealthy.")
            return healthy
        except Exception as exc:
            logger.error(f"Network self-healing error: {exc}")
            return False

    async def dns_failover_resolve(self, hostname: str) -> Optional[str]:
        """
        Layer 2: Attempt DNS resolution with fallback servers.
        Returns resolved IP or None.
        """
        import socket

        for dns in self.dns_servers:
            try:
                # Set temporary DNS resolver
                resolver = socket.getaddrinfo
                result = resolver(hostname, None)
                if result:
                    ip = result[0][4][0]
                    logger.debug(f"DNS resolved {hostname} -> {ip} via system resolver")
                    return ip
            except socket.gaierror as exc:
                logger.warning(f"DNS resolution failed for {hostname} with {dns}: {exc}")
                continue

        logger.error(f"DNS failover exhausted for {hostname}")
        return None

    async def retry_with_backoff(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        base_delay: Optional[float] = None,
        **kwargs,
    ) -> any:
        """
        Layer 3: Exponential backoff retry for API calls.
        Delay sequence: 2s, 4s, 8s, ... up to max_retries (default 5).
        Returns func result or raises last exception.
        """
        max_retries = max_retries or self.MAX_RETRIES
        base_delay = base_delay or self.BACKOFF_BASE_SECONDS
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
                last_exception = exc
                delay = base_delay * (2 ** attempt)
                jitter = random.uniform(0, delay * 0.1)
                wait_time = delay + jitter
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{max_retries}): {exc}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)
            except Exception as exc:
                # Non-retriable error
                logger.error(f"Non-retriable API error: {exc}")
                raise

        logger.error(f"All {max_retries} retry attempts exhausted.")
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry exhausted with no captured exception")

    async def platform_health_check(self, platform_url: str) -> bool:
        """
        Layer 4: Check if a platform is reachable before operations.
        Returns True if platform responds with 2xx/3xx.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(platform_url)
            is_healthy = response.status_code < 400
            if is_healthy:
                logger.info(f"Platform health check OK: {platform_url}")
            else:
                logger.warning(f"Platform health check failed: {platform_url} -> {response.status_code}")
            return is_healthy
        except Exception as exc:
            logger.warning(f"Platform health check error for {platform_url}: {exc}")
            return False
