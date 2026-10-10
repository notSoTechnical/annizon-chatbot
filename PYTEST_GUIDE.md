# Pytest Guide · Pytest 双语指南

*Bilingual guide for the Annizon chatbot test suite.*
*Annizon 聊天机器人测试套件的双语指南。*

---

## 1. What is pytest? / pytest 是什么？

**EN:** pytest is a Python test runner. You write plain functions whose names start with `test_`, and pytest finds them, runs them, and reports pass/fail. No boilerplate classes needed (unlike TestNG).

**中文：** pytest 是 Python 的测试运行器。你只管写以 `test_` 开头的普通函数，pytest 会自动找到它们、运行、报告通过 / 失败。不像 TestNG 那样需要写一堆模板类。

---

## 2. How pytest finds your tests / pytest 如何找到测试

**EN:**
- File name starts with `test_` or ends with `_test.py` → e.g. `tests/test_chatbot.py`
- Function name starts with `test_` → e.g. `def test_chunks_exist():`
- Run it: `pytest` (whole project) or `pytest tests/ -v` (`-v` = verbose, prints each test's name)

**中文：**
- 文件名以 `test_` 开头或以 `_test.py` 结尾 → 比如 `tests/test_chatbot.py`
- 函数名以 `test_` 开头 → 比如 `def test_chunks_exist():`
- 运行：`pytest`（整个项目）或 `pytest tests/ -v`（`-v` 会打印每个测试的名字）

---

## 3. `assert` — the inspector / 质检员

**EN:** `assert condition, "message"` — if the condition is `True`, the test passes silently. If `False`, the test fails and shouts the message.

```python
assert "refund" in sources, "refund policy missing"
```

**中文：** `assert 条件, "喊话"` —— 条件为真，悄悄通过；条件为假，测试失败并大喊那句话。

```python
assert "refund" in sources, "refund policy missing"
# 人话：冰箱里必须有 refund 政策，少了立刻报警
```

---

## 4. Our 5 tests, one line each / 我们的 5 个测试，一句话版

| Test / 测试 | What it guards / 它在守什么 |
|---|---|
| `test_chunks_exist` | 块数量够多，且 4 种政策（shipping / refund / privacy / terms）都在冰箱里 |
| `test_retrieval_finds_refund` | 问 "return policy" 时，找出的第一块必须是 refund 的 |
| `test_retrieval_finds_shipping` | 已知弱点：`shipping` / `shipped` 关键词匹配不上（见 §5） |
| `test_answer_uses_real_policy` | AI 的回答必须引用真实政策内容 —— 防幻觉（见 §6） |
| `test_widget_points_to_app` | 网站气泡 `widget.js` 真的指向了线上 Streamlit app |

---

## 5. `@pytest.mark.xfail` — "we know this fails" / "我们知道它会挂"

**EN:** Marks a test that is *expected* to fail. It documents a known weakness without turning CI red. Example: keyword search can't match "shipping" with "shipped" — that needs the embeddings upgrade. Once you fix it, remove the marker and the test must pass for real.

**中文：** 标记"预期会失败"的测试。用来记录已知弱点，又不让 CI 变红。例子：关键词搜索匹配不上 `shipping` / `shipped` —— 要等 embeddings 升级来修。修好后把标记去掉，测试必须真正通过。

```python
@pytest.mark.xfail(reason="keyword search can't match shipping/shipped — needs embeddings")
def test_retrieval_finds_shipping():
    ...
```

---

## 6. `@pytest.mark.skipif` — "skip when…" / "满足条件就跳过"

**EN:** Skips the test when the condition is `True`. Example: the end-to-end answer test needs a real `GEMINI_API_KEY`. On machines without the key, skip quietly instead of failing loudly.

**中文：** 条件为真时跳过这个测试。例子：端到端回答测试需要真的 `GEMINI_API_KEY`。没有 key 的机器上就悄悄跳过，而不是大声失败。

```python
@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
def test_answer_uses_real_policy():
    ...
```

---

## 7. pytest vs TestNG / pytest 对 TestNG

| | pytest | TestNG (+ Selenium) |
|---|---|---|
| Language / 语言 | Python | Java |
| What it drives / 驱动对象 | Functions, data, APIs / 函数、数据、接口 | A real browser / 真实浏览器 |
| Best at / 最擅长 | Logic, data quality, AI behavior / 逻辑、数据、AI 行为 | UI clicks, page rendering / 点击、页面渲染 |
| Speed & cost / 速度成本 | Seconds, free CI runners / 秒级，免费机器可跑 | Minutes, needs browser + driver / 分钟级，要浏览器 |
| In this project / 在本项目 | ✅ the right tool / 正好合适 | Overkill / 杀鸡用牛刀 |

**EN:** Selenium guards the storefront; pytest guards the kitchen. You now own both.
**中文：** Selenium 守门面，pytest 守厨房。你现在两个都会。

---

## 8. Nightly CI / 每夜自动巡检

**EN:** `.github/workflows/nightly.yml` runs at 2 AM ET every night:
1. Re-runs `python ingest.py` — re-downloads the 4 policy pages (verifies the store pages are still up)
2. Runs `pytest tests/ -v`

If any `assert` fails, the whole run goes red in the GitHub Actions tab.

**中文：** `.github/workflows/nightly.yml` 每天美东时间半夜 2 点运行：
1. 重跑 `python ingest.py` —— 重新下载 4 个政策页面（顺便验证店铺页面没挂）
2. 跑 `pytest tests/ -v`

任何一个 `assert` 失败，GitHub Actions 里整轮变红。

---

## 9. Cheat sheet / 作弊小抄

```bash
pytest                # run everything / 全跑
pytest tests/ -v      # verbose: show each test name / 显示每个测试名
pytest -k refund      # only tests with "refund" in the name / 只跑名字含 refund 的
pytest -x             # stop at the first failure / 第一个失败就停
pytest --lf           # re-run only the tests that failed last time / 只重跑上次挂的
```
