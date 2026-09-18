# Manual acceptance test checklist

Run \`docker compose up --build\`, import/activate n8n workflow, and watch MailHog.

1. Register Patient A and Patient B.
2. Admin login → create Doctor A and Doctor B. Note temporary passwords from MailHog.
3. Doctor A login → add Monday 09:00–11:00. Patient should see exactly four half-hour slots.
4. Patient A books one. Doctor A confirms. Verify email in MailHog.
5. Try same slot as Patient B → 409. Try same time for Patient A with Doctor B → 409 after Doctor B has matching hours.
6. POST a booking outside hours in Swagger/Postman → 400.
7. Deactivate doctor in API and verify booking blocked.
8. Try future appointment complete → 400.
9. Add leave on a day with active appointment → status cancelled and email.
10. Cancel >2h away → slot reappears. Cancel <2h → blocked.
11. Add overlapping hours / end before start / past leave → all blocked.
12. Use wrong-role tokens against doctor/admin actions → 403.
13. Try another patient's appointment and another doctor's history → 403. Admin appointment detail → 403.
14. For automation testing, create/adjust data near the reminder/expiry windows and run the two internal endpoints or n8n triggers; repeat to verify no duplicate reminder.
15. Browser DevTools mobile mode at 390px wide; verify forms, appointment cards, and dashboard remain usable.
