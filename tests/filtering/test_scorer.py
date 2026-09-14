import json
import pytest
from unittest.mock import patch, MagicMock
from filtering.scorer import score_job, run_claude_scorer
from db.models import Job


MOCK_RESPONSE = json.dumps({
    "score": 82,
    "reason": "Strong match: Python backend, microservices, 2 YOE fits",
})


class TestScoreJob:
    @patch("filtering.scorer._get_backend", return_value="gemini")
    @patch("filtering.scorer._score_with_gemini")
    def test_returns_score_and_reason_gemini(self, mock_gemini, mock_backend):
        mock_gemini.return_value = {"score": 82, "reason": "Strong match"}

        result = score_job("Backend Python Developer", "We need a backend dev...")
        assert result["score"] == 82
        assert "Strong match" in result["reason"]
        mock_gemini.assert_called_once()

    @patch("filtering.scorer._get_backend", return_value="claude")
    @patch("filtering.scorer._score_with_claude")
    def test_returns_score_and_reason_claude(self, mock_claude, mock_backend):
        mock_claude.return_value = {"score": 75, "reason": "Good match"}

        result = score_job("Backend Dev", "Python developer needed...")
        assert result["score"] == 75
        mock_claude.assert_called_once()

    @patch("filtering.scorer._get_backend", return_value="gemini")
    @patch("filtering.scorer._score_with_gemini")
    def test_handles_invalid_json(self, mock_gemini, mock_backend):
        mock_gemini.side_effect = json.JSONDecodeError("err", "doc", 0)

        result = score_job("Test", "Test JD")
        assert result["score"] == 0
        assert "error" in result["reason"].lower()

    @patch("filtering.scorer._get_backend", return_value="gemini")
    @patch("filtering.scorer._score_with_gemini")
    def test_handles_api_error(self, mock_gemini, mock_backend):
        mock_gemini.side_effect = Exception("API timeout")

        result = score_job("Test", "Test JD")
        assert result["score"] == 0
        assert "error" in result["reason"].lower()


class TestRunClaudeScorer:
    @patch("filtering.scorer._get_backend", return_value="gemini")
    @patch("filtering.scorer.score_job")
    def test_updates_status_to_scored(self, mock_score, mock_backend, db_session):
        mock_score.return_value = {"score": 85, "reason": "Great match"}

        job = Job(
            title="Backend Dev",
            company="Corp",
            url="https://naukri.com/cs/1",
            source="naukri",
            jd_text="Python backend developer needed",
            status="keyword_passed",
            keyword_score=60,
            ats_type="naukri",
        )
        db_session.add(job)
        db_session.flush()

        run_claude_scorer(db_session)

        db_session.refresh(job)
        assert job.status == "scored"
        assert job.claude_score == 85
        assert job.claude_reason == "Great match"

    @patch("filtering.scorer._get_backend", return_value="gemini")
    @patch("filtering.scorer.score_job")
    def test_updates_status_to_scored_low(self, mock_score, mock_backend, db_session):
        mock_score.return_value = {"score": 35, "reason": "Poor match"}

        job = Job(
            title="Designer",
            company="Corp",
            url="https://naukri.com/cs/2",
            source="naukri",
            jd_text="UI/UX designer",
            status="keyword_passed",
            keyword_score=42,
            ats_type="naukri",
        )
        db_session.add(job)
        db_session.flush()

        run_claude_scorer(db_session)

        db_session.refresh(job)
        assert job.status == "scored_low"
        assert job.claude_score == 35
