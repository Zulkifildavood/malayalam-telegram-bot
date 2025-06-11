import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup,ForceReply
from telegram.ext import ContextTypes

from config import ANNOTATORS, REVIEWERS
from google_sheets import sheet
from utils import is_malayalam, generate_short_id
from gspread.exceptions import APIError



def ask_for_consent(update, context):
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, I consent", callback_data='consent_yes'),
            InlineKeyboardButton("❌ No, I don’t consent", callback_data='consent_no')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Please confirm your consent to participate in this research.", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    if query.data == 'consent_yes':
        # ─── Persist the consent in your sheet ───
        records = sheet.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row.get("user_id")) == user_id:
                # update the existing row’s “consent” column (col 12)
                sheet.update_cell(idx, 12, "yes")
                break
        else:
            # new user: append with consent=yes in the 12th column
            sheet.append_row([user_id, "", "", "", "", "", "", "", "", "", "", "yes"])

        # ─── Confirmation and immediate welcome ───
        await query.edit_message_text("✅ Thank you for your consent!")
        await start(update, context)

    elif query.data == 'consent_no':
        await query.edit_message_text("❌ No worries, your data won’t be used.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)

    # 1️⃣ Check consent in your sheet…
    records = sheet.get_all_records()
    consented = any(
        str(r.get("user_id")) == user_id and r.get("consent","").lower() == "yes"
        for r in records
    )

    # 2️⃣ If not consented, prompt and exit
    if not consented:
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, I consent", callback_data='consent_yes'),
                InlineKeyboardButton("❌ No, I don’t consent", callback_data='consent_no')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return await context.bot.send_message(
            chat_id=chat_id,
            text="Please confirm your consent to participate in this research.",
            reply_markup=reply_markup
        )

    # 3️⃣ Already consented: send the usual welcome + menu
    message = (
        "🙏 <b>Welcome to the Malayalam Dialogue Collection Bot!</b>\n\n"
        "📚 <b>About this project:</b>\n"
        "This bot is part of a research project to create a high-quality dataset of Malayalam dialogues. "
        "The goal is to build a resource that can help improve AI systems like chatbots and voice assistants for Malayalam speakers.\n\n"
        "💡 <b>How it works:</b>\n"
        "1️⃣ <b>Submit Dialogues</b>\n"
        "Use the /submit command to contribute Malayalam sentences or dialogues. Make sure you type only in Malayalam script.\n"
        "<i>Example:</i>\n"
        "• \"സുപ്രഭാതം! നിങ്ങൾക്ക് എങ്ങനെ സഹായിക്കാം?\"\n"
        "• \"എനിക്ക് കേബിള്‍ കണക്ഷന്‍റെ വിശദാംശങ്ങള്‍ വേണം.\"\n\n"
        "2️⃣ <b>Annotate</b>\n"
        "If you're an assigned annotator, use /annotate to label dialogues with information like intent, emotion, and topic.\n"
        "<i>Example:</i>\n"
        "• /annotate 101 intent=question emotion=curious topic=customer_support\n\n"
        "3️⃣ <b>Review</b>\n"
        "If you're a reviewer, you can use /review to check and approve or reject the annotations.\n"
        "<i>Example:</i>\n"
        "• /review 101 status=approved comment=accurate_annotation\n\n"
        "🔎 <b>Track your progress:</b>\n"
        "Use /stats to see your total submissions.\n\n"
        "🤝 <b>Thank you for your contribution to this important research!</b>\n\n"
        "<b>Sincerely,</b>\n<b>Zulkifil Dawood</b>"
    )
    keyboard = [
        ["/submit", "/stats"],
        ["/annotate", "/review"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="HTML",
        reply_markup=reply_markup
    )



async def submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["expecting_submission"] = True
    await update.message.reply_text("📝 Please send your Malayalam sentence or dialogue now:")

async def send_annotation_options(update: Update, context: ContextTypes.DEFAULT_TYPE, dialogue_id: str):
    # Provide suggested annotations in a more descriptive format
    message_text = (
        f"📝 <b>Suggested Annotations for Dialogue ID {dialogue_id}:</b>\n"
        f"• <b>Intent</b>: request_info\n"
        f"• <b>Emotion</b>: neutral\n"
        f"• <b>Topic</b>: General\n\n"
        "👉 Would you like to accept these suggestions or edit them?"
    )

    # Provide more user-friendly buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept All", callback_data=f"accept_{dialogue_id}"),
            InlineKeyboardButton("✏️ Edit Individually", callback_data=f"edit_{dialogue_id}")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{dialogue_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
#
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("expecting_submission"):
        return await update.message.reply_text(
            "Hey you cant do that! 😅 Here’s what you can do:\n\n"
            "✅ /start – Project info\n"
            "✅ /submit – Send a Malayalam sentence/dialogue\n"
            "✅ /stats – Your submission count\n"
            "✅ /annotate – Label pending dialogues (annotators only)\n"
            "✅ /review – Review annotations (reviewers only)\n\n"
            "To begin, type /submit"
        )

    text = update.message.text.strip()
    if not is_malayalam(text):
        return await update.message.reply_text("⚠️ Please type only in Malayalam script.")

    # prepare your five columns in one shot
    user_id     = str(update.effective_user.id)
    username    = update.effective_user.username or ""
    timestamp   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dialogue_id = generate_short_id(sheet)

    try:
        # Append: user_id | username | text | timestamp | dialogue_id
        sheet.append_row([
            user_id,
            username,
            text,
            timestamp,
            dialogue_id
        ])

        context.user_data["expecting_submission"] = False
        await update.message.reply_text(
            f"✅ Saved! Your dialogue ID is <b>{dialogue_id}</b>.\n"
            "You can annotate it  later.",
            parse_mode="HTML"
        )
        #await send_annotation_options(update, context, dialogue_id)

    except APIError as e:
        logging.error(f"Error updating sheet: {e}")
        await update.message.reply_text("⚠️ Couldn’t save right now. Please try again.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")


        
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ───── Accept suggestions ─────
    if data.startswith("accept_"):
        dialogue_id = data.split("_", 1)[1]

        # persist defaults
        records = sheet.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row.get("dialogue_id")) == dialogue_id:
                sheet.update_cell(idx, 6, "request_info")  # intent
                sheet.update_cell(idx, 7, "neutral")       # emotion
                sheet.update_cell(idx, 8, "General")      # topic
                break

        # confirm & show next-steps buttons
        await query.edit_message_text(
            f"✅ <b>Annotations saved for Dialogue {dialogue_id}:</b>\n"
            f"• Intent: <code>request_info</code>\n"
            f"• Emotion: <code>neutral</code>\n"
            f"• Topic: <code>internet</code>\n\n"
            "What would you like to do next?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🆕 Annotate another", callback_data="next_annotate"),
                    InlineKeyboardButton("🏠 Main menu", callback_data="main_menu")
                ]
            ])
        )

    # ───── Edit suggestions ─────
    elif data.startswith("edit_"):
        parts = data.split("_", 2)
        if len(parts) < 3:
            await query.edit_message_text("⚠️ Invalid edit format. Please try again.")
            return
    
        field, dialogue_id = parts[1], parts[2]

    
        # Title correctly shows only the ID
        text = f"✏️ <b>Edit {field.title()}</b> for Dialogue {dialogue_id}\n\nSelect a new {field}:"
    
        # Build buttons specific to the field
        if field == "intent":
            options = ["request_info","question","greeting","complaint","feedback"]
        elif field == "emotion":
            options = ["neutral","happy","sad","angry","confused"]
        else:  # topic
            options = ["internet","customer_support","billing","technical","general"]
    
        keyboard = [
            [
                InlineKeyboardButton(opt.replace("_"," ").title(),
                                     callback_data=f"set_{field}_{dialogue_id}_{opt}")
            ]
            for opt in options
        ]
        # Add a Cancel / Back button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{dialogue_id}")])
    
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ───── Cancel flow ─────
    elif data.startswith("cancel_"):
        dialogue_id = data.split("_", 1)[1]
        try:
            await query.edit_message_text(
                f"❌ Annotation flow canceled for Dialogue {dialogue_id}.\n"
                "You can type /annotate or /start to continue.",
                parse_mode="HTML"
        )
        except Exception as e:
            logging.error(f"Failed to edit message: {e}")
            await query.message.reply_text("⚠️ Couldn’t update the annotation status.")

    # ───── Placeholders for “Next annotate” & “Main menu” ─────
    elif data == "next_annotate":
        # trigger your annotate logic (e.g. call annotate(update, context))
        await query.edit_message_text("🔄 Fetching next dialogue to annotate…")
        await annotate(update, context)

    elif data == "main_menu":
        # send the main menu (reuse your start handler)
        await query.edit_message_text("🏠 Returning to main menu…")
        await start(update, context)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    try:
        records = sheet.get_all_records()
        count = sum(1 for row in records if str(row.get("user_id", "")) == user_id)
        await update.message.reply_text(f"📊 You’ve submitted {count} entries. Keep going!")
    except Exception as e:
        logging.error(f"Error getting stats: {e}")
        await update.message.reply_text("⚠️ Couldn’t retrieve your stats. Please try again later.")

async def annotate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ANNOTATORS:
        return await update.message.reply_text("⛔ You’re not authorized to annotate.")

    # 1️⃣ Fetch all records and find the first row with empty intent/emotion/topic
    records = sheet.get_all_records()
    next_row = None
    for idx, row in enumerate(records, start=2):
        # assuming columns: dialogue_id at 5, intent at 6, emotion at 7, topic at 8
        if row.get("dialogue_id") and not row.get("intent"):
            next_row = (idx, row)
            break

    # 2️⃣ If nothing to annotate, let user know
    if not next_row:
        return await update.message.reply_text("✅ All dialogues have been annotated! No more items available.")

    row_idx, row_data = next_row
    dialogue_id = row_data["dialogue_id"]
    dialogue_text = row_data["utterance"]  # assuming column header is "message"

    # 3️⃣ Save this row_idx in user_data for callbacks to reference
    context.user_data["current_annotation"] = {"row_idx": row_idx, "dialogue_id": dialogue_id}

    # 4️⃣ Send the text + step-by-step buttons
    await update.message.reply_text(
        f"✏️ <b>Annotating Dialogue {dialogue_id}:</b>\n\n"
        f"“{dialogue_text}”\n\n"
        "Step 1/3: Choose the <b>Intent</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Request Info", callback_data="intent_request_info"),
             InlineKeyboardButton("Question",    callback_data="intent_question")],
            [InlineKeyboardButton("Greeting",      callback_data="intent_greeting"),
             InlineKeyboardButton("Complaint",   callback_data="intent_complaint")],
            [InlineKeyboardButton("Feedback",      callback_data="intent_feedback")]
        ])
    )

async def review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in REVIEWERS:
        return await update.message.reply_text("⛔ You’re not authorized to review.")

    # 1️⃣ Find the next un-reviewed row
    records = sheet.get_all_records()
    next_item = None
    for idx, row in enumerate(records, start=2):
        if row.get("dialogue_id") and not row.get("status"):
            next_item = (idx, row)
            break

    # 2️⃣ If nothing left, inform the reviewer
    if not next_item:
        return await update.message.reply_text("✅ All dialogues have been reviewed. Great job!")

    row_idx, row = next_item
    dialogue_id   = row["dialogue_id"]
    dialogue_text = row.get("utterance", "—")  # or adjust to your actual message column
    intent        = row.get("intent", "—")
    emotion       = row.get("emotion", "—")
    topic         = row.get("topic", "—")

    # 3️⃣ Save for callbacks
    context.user_data["pending_review"] = {"row_idx": row_idx, "dialogue_id": dialogue_id}

    # 4️⃣ Build the review prompt with current annotations
    text = (
        f"🕵️‍♀️ <b>Reviewing Dialogue {dialogue_id}:</b>\n\n"
        f"“{dialogue_text}”\n\n"
        f"🔍 <b>Current Annotations:</b>\n"
        f"• Intent: <code>{intent}</code>\n"
        f"• Emotion: <code>{emotion}</code>\n"
        f"• Topic: <code>{topic}</code>\n\n"
        "Do you approve these annotations?"
    )

    keyboard = [[
        InlineKeyboardButton("✅ Approve", callback_data="review_approve"),
        InlineKeyboardButton("❌ Reject",  callback_data="review_reject")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data  # either "review_approve" or "review_reject"

    info = context.user_data.get("pending_review")
    if not info:
        return await query.edit_message_text("❌ No pending review. Type /review to start again.")

    row_idx    = info["row_idx"]
    dialogue_id = info["dialogue_id"]
    reviewer_id = update.effective_user.id

    # 1) Always record who reviewed it
    sheet.update_cell(row_idx, 9, reviewer_id)

    if action == "review_approve":
        # 2a) Mark approved
        sheet.update_cell(row_idx, 10, "approved")
        sheet.update_cell(row_idx, 11, "")  # clear any comment

        # 3a) Confirm and prompt for next
        await query.edit_message_text(
            f"✅ Dialogue {dialogue_id} marked <b>approved</b>!\n\n"
            "▶️ Type /review to review the next one.",
            parse_mode="HTML"
        )
        context.user_data.pop("pending_review", None)

    else:  # "review_reject"
        # 2b) Mark rejected and ask for comment
        sheet.update_cell(row_idx, 10, "rejected")
        await query.edit_message_text(
            f"❌ Dialogue {dialogue_id} marked <b>rejected</b>.\n\n"
            "📝 Please reply to this message with your review comment:",
            parse_mode="HTML",
            reply_markup=ForceReply(selective=True)
        )

async def annotation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g. "intent_request_info" or "emotion_happy"
    field, value = data.split("_", 1)  # field = "intent", value = "request_info"

    info = context.user_data.get("current_annotation")
    if not info:
        return await query.edit_message_text("❌ Couldn’t find which dialogue you’re annotating. Please /annotate again.")

    row_idx = info["row_idx"]
    dialogue_id = info["dialogue_id"]

    # map field to column number
    col_map = {"intent": 6, "emotion": 7, "topic": 8}
    sheet.update_cell(row_idx, col_map[field], value)

    # advance to next step
    if field == "intent":
        # ask Emotion
        await query.edit_message_text(
            f"✔️ Intent set to <b>{value.replace('_',' ').title()}</b>.\n\n"
            "Step 2/3: Choose the <b>Emotion</b>:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Neutral",   callback_data="emotion_neutral"),
                 InlineKeyboardButton("Happy",     callback_data="emotion_happy")],
                [InlineKeyboardButton("Sad",       callback_data="emotion_sad"),
                 InlineKeyboardButton("Angry",     callback_data="emotion_angry")],
                [InlineKeyboardButton("Confused",  callback_data="emotion_confused")]
            ])
        )
    elif field == "emotion":
        # ask Topic
        await query.edit_message_text(
            f"✔️ Emotion set to <b>{value.title()}</b>.\n\n"
            "Step 3/3: Choose the <b>Topic</b>:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Internet",         callback_data="topic_internet"),
                 InlineKeyboardButton("Customer Support", callback_data="topic_customer_support")],
                [InlineKeyboardButton("Billing",          callback_data="topic_billing"),
                 InlineKeyboardButton("Technical",        callback_data="topic_technical")],
                [InlineKeyboardButton("General",          callback_data="topic_general")]
            ])
        )
    else:  # field == "topic"
        # finalize
        await query.edit_message_text(
            f"✅ Completed annotation for {dialogue_id}:\n"
            f"• Intent: {sheet.cell(row_idx,6).value}\n"
            f"• Emotion: {sheet.cell(row_idx,7).value}\n"
            f"• Topic: {value.replace('_',' ').title()}\n\n"
            "🎉 Great work! Use /annotate to pick the next one."
        )
        # clear it out
        context.user_data.pop("current_annotation", None)

async def handle_review_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only handle replies when we’re expecting a comment
    info = context.user_data.get("pending_review")
    if not info or update.message.reply_to_message is None:
        return  # ignore unrelated messages

    row_idx = info["row_idx"]
    dialogue_id = info["dialogue_id"]
    comment = update.message.text.strip()

    try:
        sheet.update_cell(row_idx, 11, comment)
        await update.message.reply_text(
            f"✍️ Comment saved for Dialogue {dialogue_id}.\n\n"
            "Use /review to continue."
        )
    except APIError as e:
        logging.error(f"Error saving review comment: {e}")
        await update.message.reply_text("⚠️ Couldn’t save your comment. Please try again.")
    finally:
        # Clear pending state
        context.user_data.pop("pending_review", None)


async def set_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all set_{field}_{id}_{value} callbacks."""
    query = update.callback_query
    await query.answer()
    _, field, dialogue_id, value = query.data.split("_", 3)

    # 1. find the row
    records = sheet.get_all_records()
    row_idx = next(
        (i for i, r in enumerate(records, start=2) if str(r.get("dialogue_id")) == dialogue_id),
        None
    )
    if not row_idx:
        return await query.edit_message_text("❌ Couldn’t find that dialogue. Try /annotate again.")

    # 2. map field → column index
    col_map = {"intent":6, "emotion":7, "topic":8}
    sheet.update_cell(row_idx, col_map[field], value)

    # 3. confirmation text
    text = (
        f"✔️ Updated <b>{field.title()}</b> to "
        f"<code>{value.replace('_',' ').title()}</code> for Dialogue {dialogue_id}.\n\n"
        "What next?"
    )

    # 4. next-steps buttons
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Edit Another Field", callback_data=f"edit_intent_{dialogue_id}"),
            InlineKeyboardButton("🏠 Main Menu",        callback_data="main_menu")
        ]
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)