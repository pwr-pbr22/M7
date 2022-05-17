CREATE_FUNCTION_PR_FIX_BUG = f"""
            CREATE FUNCTION prFixesBug(pr_id integer) RETURNS boolean AS $$
                DECLARE
                    pr record;
                BEGIN
                    -- check id
                    IF
                        (SELECT EXISTS(SELECT id FROM Issue_for_bug where id=pr_id))
                    THEN
                        RETURN true;
                    END IF;

                    -- check content
                    SELECT * INTO pr FROM Pull WHERE Pull.id=pr_id;
                    IF
                            pr.title ILIKE '%bug%'
                        OR
                            pr.title ILIKE '%fix%'
                        OR
                            pr.body ILIKE '%bug%'
                        OR
                            pr.body ILIKE '%fix%'
                    THEN
                        RETURN true;
                    END IF;

                    -- check referenced
                    IF
                    (
                        SELECT EXISTS
                        (
                            SELECT
                                *
                            FROM
                            (
                                (
                                    SELECT pr.id, regexp_matches(pr.title, '#(\\d+)', 'g') AS "matches"
                                )
                                UNION
                                (
                                    SELECT pr.id, regexp_matches(pr.body, '#(\\d+)', 'g') AS "matches"
                                )
                            ) AS "mi"
                            WHERE
                                CAST(mi.matches[1] AS INTEGER) IN (SELECT number FROM issue_for_bug WHERE repo_id=pr.repository_id)
                        )
                    )
                    THEN
                        RETURN true;
                    END IF;

                    RETURN false;
                END;
            $$
            Language plpgsql;
        """

CREATE_FUNCTION_NEXT_PR_FIX_BUG = """
            CREATE FUNCTION nextFixesBug(repo_id integer, filename text, starting timestamp) RETURNS boolean AS $$
                DECLARE
                    pr_id integer;
                BEGIN
                    SELECT INTO pr_id
                        p.id
                    FROM
                        File_change AS "fc"
                        JOIN Pull AS "p" ON fc.pull_id=p.id
                    WHERE
                        p.repository_id = $1 AND
                        fc.filename = $2 AND
                        p.closed_at > $3
                    ORDER BY
                        p.closed_at
                    LIMIT 1;

                    IF
                        pr_id IS NULL
                    THEN
                        RETURN null;
                    ELSE
                        RETURN prFixesBug(pr_id);
                    END IF;
                END;
            $$
            Language plpgsql;
        """


def prepare_bugginess_function_creating_string(bugginess_calculation_function: str) -> str:
    return f"""
            CREATE OR REPLACE FUNCTION bugginess(repo_id integer, filename text, starting timestamp, depth integer, pull_id integer) RETURNS decimal AS $$
                DECLARE
                    prs integer[];
                    number_of_files integer;
                    res decimal := 0;
                BEGIN
                    prs := ARRAY(
                        SELECT
                            p.id
                        FROM
                            File_change AS "fc"
                            JOIN Pull AS "p" ON fc.pull_id=p.id
                        WHERE
                            p.repository_id = $1 AND
                            fc.filename = $2 AND
                            p.created_at > $3
                        ORDER BY
                            p.created_at
                        LIMIT $4
                        );
                    SELECT
                        COUNT(*)
                    INTO
                        number_of_files
                    FROM 
                        file_change AS "fc"
                    WHERE
                        fc.repo_id = $1 AND fc.pull_id = $5;
                    raise notice 'Value: %', prs;
                    raise notice 'arr len: %', ARRAY_LENGTH(prs,1);
                    raise notice 'filename: %', $2;
                    raise notice 'created_at: %', $3;
                    IF
                        ARRAY_LENGTH(prs, 1) IS NULL
                    THEN
                        RETURN null;
                    ELSE 
                        FOR i IN 1..ARRAY_LENGTH(prs, 1) LOOP
                            IF 
                                prFixesBug(prs[i])
                            THEN
                                res := {bugginess_calculation_function};
                            END IF;
                        END LOOP;
                        RETURN res;
                    END IF;
                END;
            $$
            Language plpgsql;
        """


CREATE_OR_REPLACE_FUNCTION_BUGGINESS = prepare_bugginess_function_creating_string("res + pow(i,-2)/number_of_files")

CHECK_NULL_PR_FIX_BUG = "SELECT to_regproc('pbr.public.prFixesBug') IS NULL;"

CHECK_NULL_NEXT_PR_FIX_BUG = "SELECT to_regproc('pbr.public.nextFixesBug') IS NULL;"

CHECK_NULL_BUGGINESS = "SELECT to_regproc('pbr.public.bugginess') IS NULL;"

REVIEW_BUDDIES = """
        SELECT pull.user_id AS pull_requester, review.user_id AS reviewer
        FROM pull
             JOIN review ON pull.id = review.pull_id
             JOIN (SELECT pull.user_id pull_user_id, COUNT(*) total_reviews
                   FROM pull
                        JOIN review ON pull.id = review.pull_id
                   WHERE pull.repository_id = :repo_id
                     AND pull.user_id <> review.user_id
                   GROUP BY pull.user_id) AS user_total_reviews ON user_total_reviews.pull_user_id = pull.user_id
        WHERE pull.repository_id = :repo_id
          AND pull.user_id <> review.user_id
        GROUP BY pull.user_id, review.user_id, user_total_reviews.total_reviews
        HAVING CAST(COUNT(*) AS DECIMAL) / total_reviews > 0.5
           AND total_reviews > 50;
    """

PING_PONG = """
    select pull.id as pullId
    from pull join review on review.pull_id = pull.id
    join (select pull.user_id, pull_id, review.user_id, count(*) reviewNumber
            from pull join review on review.pull_id = pull.id  where pull.repository_id = :repo_id
            group by pull_id, review.user_id, pull.user_id) as ping_pong on ping_pong.pull_id = pull.id
    where  reviewNumber > 3 and pull.repository_id = :repo_id
     group by pull.id
           """
