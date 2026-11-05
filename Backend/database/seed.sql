DO $$
DECLARE
    sample_assessment_id INTEGER;
    employer_id INTEGER;
BEGIN
    SELECT id
    INTO sample_assessment_id
    FROM assessments
    WHERE title = 'Software Engineering Intern — Basic Coding Assessment'
    ORDER BY id
    LIMIT 1;

    IF sample_assessment_id IS NULL THEN
        SELECT id
        INTO employer_id
        FROM users
        WHERE role = 'employer'
        ORDER BY id
        LIMIT 1;

        IF employer_id IS NULL THEN
            RAISE NOTICE 'Skipping sample assessment seed: no employer account exists';
            RETURN;
        END IF;

        INSERT INTO assessments (
            title,
            description,
            technical_role,
            difficulty,
            duration,
            created_by,
            status
        )
        VALUES (
            'Software Engineering Intern — Basic Coding Assessment',
            'A foundational coding assessment for software engineering interns.',
            'SE Intern',
            'easy',
            30,
            employer_id,
            'published'
        )
        RETURNING id INTO sample_assessment_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM assessment_tasks
        WHERE assessment_id = sample_assessment_id
          AND title = 'Find Duplicate Numbers'
    ) THEN
        INSERT INTO assessment_tasks (
            assessment_id,
            title,
            description,
            task_type,
            difficulty,
            instructions,
            maximum_score,
            time_limit_seconds
        )
        VALUES (
            sample_assessment_id,
            'Find Duplicate Numbers',
            'Write a program to identify all duplicate numbers in a given integer array.',
            'coding',
            'easy',
            'Example input: [1, 2, 3, 2, 4, 5, 1]' || E'\n'
                || 'Expected output: [1, 2]',
            100,
            1800
        );
    END IF;
END;
$$;
