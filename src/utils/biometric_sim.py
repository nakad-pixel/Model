"""
Project Astra - Biometric Simulator (Layer 4)
Human-like mouse movements, typing cadences, and scroll behaviors.
"""

import asyncio
import random
from typing import List, Tuple

from src.constants import (
    MOUSE_MOVE_SLEEP_MAX,
    MOUSE_MOVE_SLEEP_MIN,
    MOUSE_STEPS_MAX,
    MOUSE_STEPS_MIN,
    TYPO_PROBABILITY,
    TYPING_DELAY_MAX_MS,
    TYPING_DELAY_MIN_MS,
)
from src.utils.logger import logger


class BiometricSimulator:
    """Mimics human biometrics to evade behavioral analysis."""

    @staticmethod
    async def mouse_move_humanized(
        page,
        x_end: int,
        y_end: int,
        overshoot: bool = True,
    ) -> None:
        """
        Move mouse to target using cubic Bezier curves with slight overshoot.
        Cursor never travels in a straight line.
        """
        start_pos = await page.mouse.get_position()
        x_start, y_start = start_pos["x"], start_pos["y"]

        # Control points for cubic Bezier curve
        cp1_x = x_start + random.uniform(-50, 50)
        cp1_y = y_start + random.uniform(-50, 50)
        cp2_x = x_end + random.uniform(-50, 50)
        cp2_y = y_end + random.uniform(-50, 50)

        # Add slight overshoot for realism
        if overshoot and random.random() < 0.3:
            x_end += random.randint(-3, 3)
            y_end += random.randint(-3, 3)

        points = BiometricSimulator._cubic_bezier(
            (x_start, y_start),
            (cp1_x, cp1_y),
            (cp2_x, cp2_y),
            (x_end, y_end),
            n_points=random.randint(20, 40),
        )

        for px, py in points:
            steps = random.randint(MOUSE_STEPS_MIN, MOUSE_STEPS_MAX)
            await page.mouse.move(px, py, steps=steps)
            await asyncio.sleep(random.uniform(MOUSE_MOVE_SLEEP_MIN, MOUSE_MOVE_SLEEP_MAX))

        # Small correction if overshot
        if overshoot:
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await page.mouse.move(x_end, y_end, steps=1)

    @staticmethod
    def _cubic_bezier(
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        n_points: int = 30,
    ) -> List[Tuple[float, float]]:
        """Generate points along a cubic Bezier curve."""
        points: List[Tuple[float, float]] = []
        for i in range(n_points + 1):
            t = i / n_points
            t_inv = 1 - t
            x = (
                t_inv**3 * p0[0]
                + 3 * t_inv**2 * t * p1[0]
                + 3 * t_inv * t**2 * p2[0]
                + t**3 * p3[0]
            )
            y = (
                t_inv**3 * p0[1]
                + 3 * t_inv**2 * t * p1[1]
                + 3 * t_inv * t**2 * p2[1]
                + t**3 * p3[1]
            )
            points.append((x, y))
        return points

    @staticmethod
    async def type_humanized(page, selector: str, text: str) -> None:
        """
        Type text with randomized delays and occasional typo simulation.
        Uses page.keyboard for more realistic input events.
        """
        logger.debug(f"Humanized typing into {selector}")
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.1, 0.3))

        for char in text:
            delay = random.randint(TYPING_DELAY_MIN_MS, TYPING_DELAY_MAX_MS)

            # Occasional typo (2% chance)
            if random.random() < TYPO_PROBABILITY and char.isalpha():
                typo_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                await page.keyboard.press(typo_char)
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.05, 0.15))

            await page.keyboard.press(char)
            await asyncio.sleep(delay / 1000)

    @staticmethod
    async def scroll_with_overshoot(page, delta_y: int = 500) -> None:
        """
        Simulate human thumb scrolling: fast start, decelerate, slight overshoot, scroll back.
        """
        # Fast initial scroll
        await page.mouse.wheel(0, delta_y)
        await asyncio.sleep(random.uniform(0.3, 0.6))

        # Slight overshoot and correction
        await page.mouse.wheel(0, random.randint(20, 50))
        await asyncio.sleep(random.uniform(0.2, 0.4))

        # Scroll back slightly (reading simulation)
        await page.mouse.wheel(0, random.randint(-30, -10))
        await asyncio.sleep(random.uniform(0.5, 1.0))

    @staticmethod
    async def sweep_mouse_to_center(page) -> None:
        """
        Sweep mouse in an arc toward the center of the viewport.
        Used after page loads to simulate human attention.
        """
        viewport = page.viewport_size
        if viewport:
            center_x = viewport["width"] // 2
            center_y = viewport["height"] // 2
            await BiometricSimulator.mouse_move_humanized(
                page, center_x, center_y, overshoot=False
            )
            await asyncio.sleep(random.uniform(0.5, 1.5))
