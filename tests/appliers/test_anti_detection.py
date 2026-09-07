from appliers.anti_detection import (
    get_random_user_agent,
    get_random_viewport,
    random_delay,
    get_keystroke_delay,
    USER_AGENTS,
    VIEWPORTS,
)


class TestAntiDetection:
    def test_user_agent_is_from_pool(self):
        ua = get_random_user_agent()
        assert ua in USER_AGENTS
        assert "Chrome" in ua or "Mozilla" in ua

    def test_viewport_is_from_pool(self):
        vp = get_random_viewport()
        assert vp in VIEWPORTS
        assert "width" in vp
        assert "height" in vp

    def test_random_delay_within_range(self):
        for _ in range(20):
            delay = random_delay(1.0, 2.0)
            assert 1.0 <= delay <= 2.0

    def test_keystroke_delay_within_range(self):
        for _ in range(20):
            delay = get_keystroke_delay()
            assert 50 <= delay <= 150

    def test_user_agent_pool_has_enough_entries(self):
        assert len(USER_AGENTS) >= 10

    def test_viewport_pool_has_enough_entries(self):
        assert len(VIEWPORTS) >= 4
