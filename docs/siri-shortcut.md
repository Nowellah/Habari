# "Hey Siri, Habari" (status: Planned)

The server side is ready: `POST /api/channel/siri` takes the same JSON as every other channel. The iPhone Shortcut still has to be built and tested on a real iPhone.

## Build the Shortcut on an iPhone

1. Open the **Shortcuts** app, tap **+**, and name the shortcut **Habari**.
2. Add **Dictate Text** (language: the child's language).
3. Add **Text** and type a random id, for example `siri-` followed by 12 random letters. This lets the child follow up without a name.
4. Add **Get Contents of URL**:
   - URL: `PUBLIC_BASE_URL/api/channel/siri` (the ngrok https address while testing)
   - Method: **POST**, Request Body: **JSON**
   - Fields: `channel` = `siri`, `sender_id` = the Text from step 3, `text` = Dictated Text
5. Add **Get Dictionary Value**, key `reply_text`.
6. Add **Speak Text** with that value. Optionally add **Show Result**.
7. In the shortcut's settings, turn on **Show in Share Sheet**, so it can also receive a link shared from TikTok or Instagram.
8. Say **"Hey Siri, Habari"** and speak.

## Test

- Say "Help". Siri should read the five choices.
- Say "I want to die". Siri should read "Call 116 now, it is free…" and a case code should appear in the officer queue with channel `siri`.

## Share with testers

In the shortcut's menu choose **Share > Copy iCloud Link**. Only label this feature **Built** after it has been run on an iPhone.

## Android

Android uses the installable web app instead: its home-screen shortcut **Speak to Habari** opens `/voice`.
