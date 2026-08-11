"""
Unit and pilot tests for ConsumptionSidebar widget rendering.
"""

import unittest
from textual.app import App, ComposeResult
from agent.terminal_ui.sidebar import ConsumptionSidebar


class SidebarTestApp(App):
    def compose(self) -> ComposeResult:
        yield ConsumptionSidebar(id="test_sidebar")


class TestConsumptionSidebar(unittest.TestCase):

    def test_sidebar_initialization_and_update(self):
        app = SidebarTestApp()

        async def run_sidebar_test():
            async with app.run_test() as pilot:
                sidebar = app.query_one("#test_sidebar", ConsumptionSidebar)
                self.assertIsNotNone(sidebar)

                test_metrics = {
                    "last_prompt_tokens": 1500,
                    "last_completion_tokens": 500,
                    "last_cost": 0.0088,
                    "session_prompt_tokens": 3000,
                    "session_completion_tokens": 1000,
                    "session_cost": 0.0176,
                    "total_requests": 2,
                    "current_context_tokens": 25000,
                    "max_context_limit": 128000,
                    "context_percent": 19.5,
                }

                sidebar.update_metrics(test_metrics, session_name="Test Session Title", project_name="test-project")
                await pilot.pause()

                rendered = str(sidebar.metrics_static.render())
                self.assertIn("WORKSPACE & SESSION", rendered)
                self.assertIn("test-project", rendered)
                self.assertIn("Test Session Title", rendered)
                self.assertIn("CONSUMPTION METRICS", rendered)
                self.assertIn("19.5%", rendered)
                self.assertIn("1,500", rendered)
                self.assertIn("0.0088", rendered)

        import asyncio
        asyncio.run(run_sidebar_test())


if __name__ == "__main__":
    unittest.main()
