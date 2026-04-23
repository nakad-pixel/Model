"""
Project Astra - WARP Manager (Layer 1)
Cloudflare WARP CLI wrapper for network obfuscation and IP rotation.
"""

import asyncio
import subprocess
from typing import Optional

import httpx

from src.utils.logger import logger


class WarpManager:
    """Manages Cloudflare WARP VPN connection for traffic obfuscation."""

    def __init__(self) -> None:
        self.connected = False

    async def install(self) -> bool:
        """Install Cloudflare WARP CLI on Ubuntu."""
        try:
            logger.info("Installing Cloudflare WARP...")
            cmds = [
                ["sudo", "apt-get", "update", "-qq"],
                ["sudo", "apt-get", "install", "-y", "-qq", "curl", "gnupg"],
                [
                    "bash",
                    "-c",
                    "curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg",
                ],
                [
                    "bash",
                    "-c",
                    'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ jammy main" | sudo tee /etc/apt/sources.list.d/cloudflare-warp.list',
                ],
                ["sudo", "apt-get", "update", "-qq"],
                ["sudo", "apt-get", "install", "-y", "-qq", "cloudflare-warp"],
            ]
            for cmd in cmds:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    logger.warning(f"WARP install step failed: {stderr.decode()[:200]}")
            logger.info("Cloudflare WARP installation complete.")
            return True
        except Exception as exc:
            logger.error(f"WARP install error: {exc}")
            return False

    async def register(self) -> bool:
        """Register WARP client."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "warp-cli", "--accept-tos", "register",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode in (0, 1):  # 1 often means already registered
                logger.info("WARP registered.")
                return True
            logger.warning(f"WARP register stderr: {stderr.decode()[:200]}")
            return False
        except Exception as exc:
            logger.error(f"WARP register error: {exc}")
            return False

    async def connect(self) -> bool:
        """Connect to WARP and verify connection."""
        try:
            logger.info("Connecting to WARP...")
            proc = await asyncio.create_subprocess_exec(
                "warp-cli", "--accept-tos", "set-mode", "warp",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            proc = await asyncio.create_subprocess_exec(
                "warp-cli", "--accept-tos", "connect",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            # Wait for connection stabilization
            await asyncio.sleep(5)

            verified = await self.verify_connection()
            self.connected = verified
            return verified
        except Exception as exc:
            logger.error(f"WARP connect error: {exc}")
            return False

    async def verify_connection(self) -> bool:
        """Verify WARP is active by querying Cloudflare trace endpoint."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get("https://www.cloudflare.com/cdn-cgi/trace")
            body = response.text
            if "warp=on" in body:
                logger.info("WARP connection verified: warp=on")
                return True
            elif "warp=plus" in body:
                logger.info("WARP connection verified: warp=plus")
                return True
            logger.warning(f"WARP not active. Trace response: {body[:200]}")
            return False
        except Exception as exc:
            logger.error(f"WARP verification error: {exc}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from WARP."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "warp-cli", "--accept-tos", "disconnect",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            self.connected = False
            logger.info("WARP disconnected.")
        except Exception as exc:
            logger.error(f"WARP disconnect error: {exc}")

    async def rotate_ip(self) -> bool:
        """Rotate exit node by disconnecting and reconnecting."""
        logger.info("Rotating WARP exit node...")
        await self.disconnect()
        await asyncio.sleep(2)
        return await self.connect()
