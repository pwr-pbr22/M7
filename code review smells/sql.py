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
