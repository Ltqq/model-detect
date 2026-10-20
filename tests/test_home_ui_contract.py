from importlib.resources import files


def test_home_page_uses_one_responsive_theme():
    html = files("model_detect").joinpath("templates/index.html").read_text(encoding="utf-8")
    css = html.split("<style>", 1)[1].split("</style>", 1)[0]
    assert css.count(":root") == 1
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "@media(max-width:820px)" in css


def test_home_page_does_not_overstate_reference_or_provider_evidence():
    html = files("model_detect").joinpath("templates/index.html").read_text(encoding="utf-8")
    assert "可增强模型身份判断" not in html
    assert "综合分 ≠ 模型为真的概率" not in html
    assert "Header / Body 指纹" not in html
    assert "生成正文、推理文本和自由文本错误不用于猜测供应商" in html
    assert "不证明模型权重身份" in html
