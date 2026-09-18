# n8n automations
Import \`clinic-automation.json\` in n8n (http://localhost:5678).

The workflow contains:
1. Webhook \`POST /webhook/clinic-email\` for confirmation/cancellation/rejection/reminder/doctor-invite emails.
2. Every-10-minutes call to API \`/internal/automation/expire-pending\`.
3. Hourly call to API \`/internal/automation/reminders\`.

SMTP is configured for local MailHog (\`mailhog:1025\`). For real email, replace the SMTP credential/node configuration with Gmail/SMTP and keep the same event payloads.
