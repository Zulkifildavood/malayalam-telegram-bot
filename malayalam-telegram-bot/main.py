import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config import BOT_TOKEN
from handlers import (
    start,
    submit,
    handle_message,
    stats,
    annotate,
    review,
    # Consent buttons
    button_callback,
    # Annotation multi-step
    annotation_callback,
    # Review multi-step
    review_callback,
    handle_review_comment,
    # Field edit callbacks
    set_field_callback,
    button_handler

)

def main():
    # 1️⃣ Logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    # 2️⃣ Build the bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 3️⃣ Command handlers
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("submit",   submit))
    app.add_handler(CommandHandler("stats",    stats))
    app.add_handler(CommandHandler("annotate", annotate))
    app.add_handler(CommandHandler("review",   review))

    # 4️⃣ Message handler for plain text (submissions & review comments)
    #    - submission texts get routed to handle_message
    #    - reply-to messages after a reject go to handle_review_comment
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY,      handle_review_comment))

    # 5️⃣ CallbackQuery handlers (in priority order)

    # – Consent flow
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^consent_"))

    # – Annotation flow (step 1/3 Intent, 2/3 Emotion, 3/3 Topic)
    app.add_handler(CallbackQueryHandler(annotation_callback, pattern="^annotate_"))
    app.add_handler(CallbackQueryHandler(annotation_callback, pattern="^(intent|emotion|topic)_"))

    # – Inline “Edit Annotations” submenu
    app.add_handler(CallbackQueryHandler(button_handler,    pattern="^edit_"))
    app.add_handler(CallbackQueryHandler(set_field_callback, pattern="^set_(intent|emotion|topic)_"))

    # – Review flow (approve/reject buttons)
    app.add_handler(CallbackQueryHandler(review_callback, pattern="^review_(approve|reject)$"))
    # – Post-review navigation
    app.add_handler(CallbackQueryHandler(lambda u,c: review(u,c), pattern="^review_next$"))
    app.add_handler(CallbackQueryHandler(lambda u,c: start(u,c),  pattern="^main_menu$"))

    # 6️⃣ Start polling
    logging.info("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()