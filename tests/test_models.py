from detective.models import Cause, Diagnosis, FailureReport, FixProposal, ReproResult


def test_pipeline_contracts_preserve_stage_data() -> None:
    report = FailureReport(
        test_id="tests/test_example.py::test_flaky",
        error_message="assert 1 == 2",
        stack_trace="Traceback...",
        run_metadata={"runner_os": "ubuntu"},
    )
    repro = ReproResult(
        test_id=report.test_id,
        matrix={"random_order": 0.5},
        sample_failures=[report.error_message],
    )
    diagnosis = Diagnosis(
        cause=Cause.SHARED_STATE,
        confidence=0.9,
        evidence=["Fails only under random order."],
        suspect_lines=[12],
    )
    proposal = FixProposal(
        diff="--- a/test_example.py",
        explanation_md="Reset shared state for each test.",
        validation_matrix={"random_order": 0.0},
    )

    assert repro.test_id == report.test_id
    assert diagnosis.cause is Cause.SHARED_STATE
    assert proposal.validation_matrix["random_order"] == 0.0
