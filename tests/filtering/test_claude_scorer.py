import json
import pytest
from unittest.mock import patch, MagicMock
from filtering.claude_scorer import score_job_with_claude, run_claude_scorer
from db.models import Job


MOCK_CLAUDE_RESPONSE = json.dumps({
    "score": 82,
    "reason": "Strong match: Python backend, microservices, 2 YOE fits",
})


class TestScoreJobWithClaude:
    @patch("filtering.claude_scorer.client")
    def test_returns_score_and_reason(self, mock_client):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=MOCK_CLAUDE_RESPONSE)]
        mock_client.messages.create.return_value = mock_message

        result = score_job_with_claude("Backend Python Developer", "We need a backend dev...")
        assert result["score"] == 82
        assert "Strong match" in result["reason"]

    @patch("filtering.claude_scorer.client")
    def test_handles_invalid_json(self, mock_client):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Not valid JSON")]
        mock_client.messages.create.return_value = mock_message

        result = score_job_with_claude("Test", "Test JD")
        assert result["score"] == 0
        assert "parse" in result["reason"].lower() or "error" in result["reason"].lower()

    @patch("filtering.claude_scorer.client")
    def test_handles_api_error(self, mock_client):
        mock_client.messages.create.side_effect = Exception("API timeout")

        result = score_job_with_claude("Test", "Test JD")
        assert result["score"] == 0
        assert "error" in result["reason"].lower()


class TestRunClaudeScorer:
    @patch("filtering.claude_scorer.score_job_with_claude")
    def test_updates_status_to_scored(self, mock_score, db_session):
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

    @patch("filtering.claude_scorer.score_job_with_claude")
    def test_updates_status_to_scored_low(self, mock_score, db_session):
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
