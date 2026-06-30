"""Unit tests for domain exceptions."""

from __future__ import annotations

import pytest

from backend.domain.exceptions import (
    DomainError,
    DomainValidationError,
    InvalidClipRangeError,
    InvalidExportStateError,
    InvalidPluginStateError,
    InvalidProjectStateError,
    InvalidQualityScoreError,
    InvalidStateTransitionError,
    InvalidTimestampError,
    InvalidVideoFormatError,
    InvalidVideoStateError,
)


class TestDomainError:
    def test_base_exception(self) -> None:
        err = DomainError("ERR-TEST", "Test message", {"key": "value"})
        assert err.code == "ERR-TEST"
        assert err.message == "Test message"
        assert err.details == {"key": "value"}
        assert str(err) == "[ERR-TEST] Test message"

    def test_to_dict(self) -> None:
        err = DomainError("ERR-TEST", "Test")
        d = err.to_dict()
        assert d["code"] == "ERR-TEST"
        assert d["message"] == "Test"
        assert d["details"] == {}

    def test_is_exception(self) -> None:
        assert issubclass(DomainError, Exception)


class TestDomainValidationError:
    def test_default_code(self) -> None:
        err = DomainValidationError("Invalid")
        assert err.code == "ERR-DOMAIN-VALIDATION"

    def test_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            raise DomainValidationError("test")


class TestInvalidTimestampError:
    def test_default_message(self) -> None:
        err = InvalidTimestampError()
        assert "Invalid timestamp range" in err.message

    def test_raises(self) -> None:
        with pytest.raises(InvalidTimestampError):
            raise InvalidTimestampError()


class TestInvalidClipRangeError:
    def test_default_message(self) -> None:
        err = InvalidClipRangeError()
        assert "Invalid clip range" in err.message


class TestInvalidQualityScoreError:
    def test_default_message(self) -> None:
        err = InvalidQualityScoreError()
        assert "Invalid quality score" in err.message


class TestInvalidVideoFormatError:
    def test_default_message(self) -> None:
        err = InvalidVideoFormatError()
        assert "Unsupported video format" in err.message


class TestInvalidStateTransitionError:
    def test_message_format(self) -> None:
        err = InvalidStateTransitionError("Project", "created", "deleted")
        assert "Project" in err.message
        assert "created" in err.message
        assert "deleted" in err.message
        assert err.details["entity_type"] == "Project"
        assert err.details["current_state"] == "created"
        assert err.details["target_state"] == "deleted"


class TestInvalidProjectStateError:
    def test_inheritance(self) -> None:
        assert issubclass(InvalidProjectStateError, InvalidStateTransitionError)


class TestInvalidVideoStateError:
    def test_inheritance(self) -> None:
        assert issubclass(InvalidVideoStateError, InvalidStateTransitionError)


class TestInvalidExportStateError:
    def test_inheritance(self) -> None:
        assert issubclass(InvalidExportStateError, InvalidStateTransitionError)


class TestInvalidPluginStateError:
    def test_inheritance(self) -> None:
        assert issubclass(InvalidPluginStateError, InvalidStateTransitionError)
