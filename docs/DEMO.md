# 90-second demonstration

1. **0–20 seconds.** Start `python -X utf8 -B app.py`, open the assistant and ask “How many tools can I borrow?” Follow the **Borrowing limits** citation to show the exact approved answer.
2. **20–40 seconds.** Ask “Can I reserve a bike repair stand?” Select the save checkbox before submitting. Show the fallback and open the fictional support route.
3. **40–70 seconds.** Open **FAQ editor** and show the unanswered queue. Add a draft titled “Repair stand” with the alias `bike repair stand` and the answer “Ask the staffed desk about repair stand availability.” Show that the draft is absent from visitor retrieval, then approve it and repeat the question.
4. **70–90 seconds.** Run `python -X utf8 -B evaluate.py`. Explain that it starts with the fixed synthetic corpus in a fresh database and checks routing and sources. The chatbot uses deterministic retrieval. The human support page is a demonstration.
