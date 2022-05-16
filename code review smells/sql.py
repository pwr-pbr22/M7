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
                            pr.title ILIKE '%error%'
                        OR
                            pr.title ILIKE '%fix%'
                        OR
                            pr.body ILIKE '%bug%'
                        OR
                            pr.body ILIKE '%error%'
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

CHECK_NULL_PR_FIX_BUG = "SELECT to_regproc('pbr.public.prFixesBug') IS NULL;"

CHECK_NULL_NEXT_PR_FIX_BUG = "SELECT to_regproc('pbr.public.nextFixesBug') IS NULL;"

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