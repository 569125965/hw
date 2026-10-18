from app.providers.social import heat_score_from_rank, _sentiment_of, _polarity_score


def test_heat_rank_top_is_hot():
    assert heat_score_from_rank(1) >= 98
    assert heat_score_from_rank(3) >= 90
    assert heat_score_from_rank(10) >= 80
    assert heat_score_from_rank(3) > heat_score_from_rank(50)
    assert heat_score_from_rank(50) > heat_score_from_rank(500)


def test_controversy_keywords_negative():
    assert _sentiment_of("三部门联合调查尊界V800刹车争议") == "negative"
    assert _sentiment_of("懂车帝下架尊界V800测试相关视频") == "negative"
    assert _sentiment_of("公司回购股份获市场看好") == "positive"


def test_polarity_not_diluted_by_neutral_hot_posts():
    guba = [
        {"sentiment": "negative", "click": 50000, "comment": 200},
        {"sentiment": "neutral", "click": 10000, "comment": 10},
        {"sentiment": "neutral", "click": 8000, "comment": 5},
    ]
    score = _polarity_score(guba, guba)
    assert score < 45
