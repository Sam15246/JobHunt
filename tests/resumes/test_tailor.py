import os
import pytest
from unittest.mock import patch, MagicMock
from resumes.tailor import tailor_resume, _load_base_resume
from resumes.pdf_gen import _parse_resume_text, generate_pdf


class TestTailorResume:
    @patch("resumes.tailor.GROQ_API_KEY", "fake-key")
    @patch("resumes.tailor._tailor_with_groq")
    def test_calls_groq_and_returns_text(self, mock_groq):
        mock_groq.return_value = "SYED ALI MUJTABA\nTailored headline\n\nTECHNICAL SKILLS\n- Java"
        result = tailor_resume("Software Engineer", "Mastercard", "We need a Java developer...")
        assert "SYED ALI MUJTABA" in result
        mock_groq.assert_called_once()

    @patch("resumes.tailor.GROQ_API_KEY", "")
    @patch("resumes.tailor.GEMINI_API_KEY", "")
    @patch("resumes.tailor.ANTHROPIC_API_KEY", "")
    def test_raises_without_api_key(self):
        with pytest.raises(RuntimeError, match="No API key"):
            tailor_resume("Software Engineer", "Mastercard", "JD text")

    @patch("resumes.tailor.GROQ_API_KEY", "fake-key")
    @patch("resumes.tailor._tailor_with_groq")
    def test_strips_markdown_fences(self, mock_groq):
        mock_groq.return_value = "```\nSYED ALI MUJTABA\nContent\n```"
        result = tailor_resume("SWE", "MC", "JD")
        assert not result.startswith("```")
        assert "SYED ALI MUJTABA" in result


class TestLoadBaseResume:
    def test_loads_base_resume_file(self):
        text = _load_base_resume()
        assert "SYED ALI MUJTABA" in text
        assert "TECHNICAL SKILLS" in text
        assert "EXPERIENCE" in text


class TestParseResumeText:
    def test_identifies_sections(self):
        text = "SYED ALI MUJTABA\nTagline here\n\nTECHNICAL SKILLS\n- Java\n- Python\n\nEXPERIENCE\n- Built APIs"
        blocks = _parse_resume_text(text)
        types = [b[0] for b in blocks]
        assert "section" in types
        assert "bullet" in types

    def test_identifies_bullets(self):
        blocks = _parse_resume_text("- First bullet\n* Second bullet")
        assert all(b[0] == "bullet" for b in blocks)
        assert blocks[0][1] == "First bullet"
        assert blocks[1][1] == "Second bullet"


class TestGeneratePdf:
    def test_creates_pdf_file(self, tmp_path):
        text = "SYED ALI MUJTABA\nBackend Engineer\n\nTECHNICAL SKILLS\n- Java\n- Python\n\nEXPERIENCE\n- Built APIs"
        output = str(tmp_path / "test_resume.pdf")
        result = generate_pdf(text, output)
        assert os.path.exists(result)
        assert result.endswith(".pdf")
        assert os.path.getsize(result) > 0
