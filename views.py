"""Server-rendered HTML for the local support demonstration."""

from html import escape


EXAMPLES = ("How many tools can I borrow?", "How do I return a tool?", "When are you open?")


def page(title, body, *, admin=False):
    menu = (
        '<a href="/" aria-current="page">Assistant</a><a href="/editor">FAQ editor</a>'
        if not admin else
        '<a href="/">Assistant</a><a href="/editor" aria-current="page">FAQ editor</a>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · Alderbank Tool Library</title>
<link rel="stylesheet" href="/static/style.css"></head>
<body><header><div class="bar">
<a class="brand" href="/"><span class="mark" aria-hidden="true">A</span>Alderbank Tool Library</a>
<nav aria-label="Main">{menu}</nav></div></header>
<main>{body}</main>
<footer>Fictional organization · Local demonstration</footer>
</body></html>"""


def nonce(value):
    return f'<input type="hidden" name="token" value="{escape(value)}">'


def chat(token, *, question="", reply=None, tracked=False):
    examples = "".join(f'<li>{escape(text)}</li>' for text in EXAMPLES)
    conversation = """<div class="message assistant"><strong>Alderbank assistant</strong>
<p>Hi! Ask about borrowing, returning tools, orientation, or opening hours.</p></div>"""
    if reply:
        source = ""
        if reply.article:
            article = reply.article
            source = (f'<a class="source" href="/source/{article["id"]}">'
                      f'Approved FAQ · {escape(article["title"])}</a>')
        else:
            source = '<a class="source" href="/help">See human support options</a>'
        notice = '<p class="notice">Added to the local unanswered queue.</p>' if tracked else ""
        conversation = f"""<div class="message visitor"><strong>You</strong>
<p>{escape(question)}</p></div>
<div class="message assistant"><strong>Alderbank assistant</strong>
<p>{escape(reply.text)}</p>{source}{notice}</div>"""
    return page("Support assistant", f"""
<section class="intro">
<h1>Tool library support</h1>
<p>Get answers from the library’s approved FAQs.</p>
</section>
<div class="chat-layout">
<section class="panel chat" aria-label="Conversation">{conversation}
<form method="post" action="/ask" class="compose">{nonce(token)}
<label for="question">Your question</label>
<div class="input-row"><input id="question" name="question" required maxlength="240"
placeholder="Ask about your visit"><button>Ask</button></div>
<label class="check"><input type="checkbox" name="track" value="yes">
Save this question locally if unanswered</label></form></section>
<aside class="panel sidebar"><h2>Try a question</h2><ul>{examples}</ul>
<a href="/help">Human support</a></aside></div>""")


def source(article):
    return page("Approved FAQ", f"""<section class="intro"><p><a href="/">Back to assistant</a></p>
<h1>{escape(article["title"])}</h1></section><article class="panel article">
<p class="status approved">Approved FAQ · Revision {article["revision"]}</p>
<p>{escape(article["answer"])}</p></article>""")


def help_page():
    return page("Human support", """<section class="intro"><h1>Human support</h1>
<p>Visit the staffed desk during opening hours to ask a team member.</p></section>
<section class="panel article"><h2>Demo handoff</h2>
<p>This fictional support route provides guidance only. It does not send a message or create a ticket.</p>
<a href="/">Back to assistant</a></section>""")


def article_form(token, article=None):
    hidden = ""
    title = response = aliases = ""
    button = "Create draft"
    if article:
        hidden = (f'<input type="hidden" name="id" value="{article["id"]}">'
                  f'<input type="hidden" name="revision" value="{article["revision"]}">')
        title, response = escape(article["title"]), escape(article["answer"])
        aliases = escape("\n".join(article["aliases"]))
        button = "Save as draft"
    return f"""<form method="post" action="/editor/save" class="edit-form">{nonce(token)}{hidden}
<label>FAQ title<input name="title" maxlength="90" value="{title}" required></label>
<label>Answer<textarea name="answer" maxlength="700" rows="3" required>{response}</textarea></label>
<label>Search aliases, one per line<textarea name="aliases" maxlength="608" rows="3" required>{aliases}</textarea></label>
<button>{button}</button></form>"""


def editor(token, articles, unanswered, *, problem=""):
    blocks = []
    for article in articles:
        label = "Approved" if article["approved"] else "Draft"
        action = "Unpublish" if article["approved"] else "Approve"
        blocks.append(f"""<article class="faq">
<div class="faq-heading"><h3>{escape(article["title"])}</h3><span class="status {label.lower()}">{label}</span></div>
<p>{escape(article["answer"])}</p>
<details><summary>Edit FAQ</summary>{article_form(token, article)}</details>
<form method="post" action="/editor/approval">{nonce(token)}
<input type="hidden" name="id" value="{article["id"]}">
<input type="hidden" name="revision" value="{article["revision"]}">
<button class="secondary" name="approved" value="{int(not article["approved"])}">{action}</button></form></article>""")
    reasons = {"no_match": "No approved match", "ambiguous": "Multiple topics"}
    entries = "".join(f'<li><span>{escape(item["question"])}</span>'
                      f'<small>{escape(reasons.get(item["reason"], item["reason"]))}</small></li>'
                      for item in unanswered)
    queue = f"""<ul class="queue">{entries}</ul><form method="post" action="/editor/clear">
{nonce(token)}<button class="secondary">Clear queue</button></form>""" if entries else "<p>No saved questions.</p>"
    banner = f'<p role="alert" class="error">{escape(problem)}</p>' if problem else ""
    return page("FAQ editor", f"""<section class="intro">
<h1>FAQ editor</h1><p>Review answers before visitors can retrieve them. Editing sends an approved FAQ back to draft.</p>
</section>{banner}<div class="editor-layout">
<section class="panel catalog"><h2>Knowledge base</h2>
<details class="new"><summary>Add FAQ</summary>{article_form(token)}</details>
{"".join(blocks)}</section>
<aside class="panel sidebar"><h2>Unanswered questions</h2>
<p>Visitors choose whether to save a question when the assistant cannot answer.</p>
{queue}</aside></div>""", admin=True)
