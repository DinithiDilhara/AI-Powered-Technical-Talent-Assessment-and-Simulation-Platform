import unittest
from datetime import datetime
from decimal import Decimal

from pydantic import ValidationError

from app.schemas import (
    AssessmentRole,
    AssessmentTaskCreate,
    AssessmentTaskResponse,
    AssessmentTaskType,
)


class AssessmentRoleTests(unittest.TestCase):
    def test_supported_technical_roles_are_distinct_from_platform_roles(self):
        self.assertEqual(
            {role.value for role in AssessmentRole},
            {
                "SE Intern",
                "SE",
                "SSE",
                "AI Intern",
                "AI Engineer",
                "DevOps Intern",
                "DevOps Engineer",
            },
        )


class AssessmentTaskSchemaTests(unittest.TestCase):
    def test_valid_coding_task(self):
        task = AssessmentTaskCreate(
            assessment_id=1,
            title="Find Duplicate Numbers",
            description="Find all duplicated integers in an array.",
            task_type="coding",
            difficulty="easy",
            instructions="Return the duplicate values.",
            maximum_score=100,
            time_limit_seconds=1800,
        )

        self.assertEqual(task.task_type, AssessmentTaskType.coding)
        self.assertEqual(task.maximum_score, Decimal("100"))

    def test_valid_iq_task_without_time_limit(self):
        task = AssessmentTaskCreate(
            assessment_id=1,
            title="Number sequence",
            description="Determine the next number.",
            task_type="IQ",
            difficulty="medium",
            instructions="Explain your answer.",
            maximum_score=25,
        )

        self.assertEqual(task.task_type, AssessmentTaskType.iq)
        self.assertIsNone(task.time_limit_seconds)

    def test_invalid_type_difficulty_and_assessment_reference_are_rejected(self):
        task_data = {
            "assessment_id": 1,
            "title": "Sample",
            "description": "Sample description",
            "task_type": "written",
            "difficulty": "easy",
            "instructions": "Complete the task.",
            "maximum_score": 10,
        }
        with self.assertRaises(ValidationError):
            AssessmentTaskCreate(**task_data)

        task_data["task_type"] = "coding"
        task_data["difficulty"] = "extreme"
        with self.assertRaises(ValidationError):
            AssessmentTaskCreate(**task_data)

        task_data["difficulty"] = "easy"
        task_data["assessment_id"] = 0
        with self.assertRaises(ValidationError):
            AssessmentTaskCreate(**task_data)

    def test_required_fields_and_positive_limits_are_enforced(self):
        with self.assertRaises(ValidationError):
            AssessmentTaskCreate(
                assessment_id=1,
                title=" ",
                description="Description",
                task_type="coding",
                difficulty="easy",
                instructions="Instructions",
                maximum_score=0,
                time_limit_seconds=0,
            )

        with self.assertRaises(ValidationError):
            AssessmentTaskCreate(
                assessment_id=1,
                title="Task",
                task_type="coding",
                difficulty="easy",
                instructions="Instructions",
                maximum_score=10,
            )

    def test_task_response_includes_persisted_relationship_and_timestamps(self):
        created_at = datetime(2026, 1, 1)
        response = AssessmentTaskResponse(
            id=5,
            assessment_id=2,
            title="Sample",
            description="Sample description",
            task_type="coding",
            difficulty="easy",
            instructions="Complete the task.",
            maximum_score=10,
            created_at=created_at,
            updated_at=created_at,
        )

        self.assertEqual(response.assessment_id, 2)
        self.assertEqual(response.created_at, created_at)
        self.assertEqual(response.updated_at, created_at)


if __name__ == "__main__":
    unittest.main()
