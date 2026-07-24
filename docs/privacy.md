# Privacy Policy — DevRadar

**Last updated:** 2026-07-24  
**Project:** [DevRadar](https://github.com/bagusardin25/DevRadar)

This policy describes how a typical DevRadar deployment may handle data. If you self-host, **you** are the data controller for your instance; adjust this page accordingly for production.

## 1. Summary

- **Public catalogue:** browsing hackathons and AI offers does not require an end-user account.  
- **Optional email alerts:** if you subscribe, your email may be stored in encrypted form and used only to deliver opportunity alerts you requested.  
- **Admin operators:** may authenticate via OAuth (e.g. GitHub); only allowlisted accounts get admin access.  
- **X / Twitter developer tools:** API keys and OAuth tokens used by operators stay on server/config and are **not** collected from end users of the public site.

## 2. Data we may process

| Category | Examples | Purpose |
|---|---|---|
| Technical logs | IP (hashed where designed), request metadata | Security, abuse prevention, debugging |
| Alert subscriptions | Email (encrypted at rest where implemented), preferences | Send confirmation and alerts |
| Admin sessions | Session cookie, GitHub user id | Secure admin review queue |
| Ingestion data | Public page text, listing fields, source URLs | Build and verify the catalogue |
| Operator secrets | API keys in environment variables | Server-side fetch / LLM / X API |

We do **not** require end users to paste OpenAI, Anthropic, or X API keys into the public web UI.

## 3. Cookies and local storage

- **Admin:** session cookies when an operator logs in.  
- **Public UI:** preferences and bookmarks may use **browser localStorage** only on the client device (not a server account).

## 4. Third parties

Depending on configuration, a deployment may call:

- **Hosting / database / email** providers you choose  
- **OpenAI** (or other LLM) for structured extraction of **already fetched** page text (not end-user chat)  
- **X (Twitter) API** for operator-led discovery of public posts and links  
- **GitHub** for admin OAuth  

Those services process data under their own policies.

## 5. Retention

- Listings and verification history: retained while useful for the catalogue.  
- Alert subscriptions: until you unsubscribe or the operator deletes them.  
- Logs: short operational retention unless longer retention is required for security.

## 6. Your choices

- Do not subscribe if you do not want email stored.  
- Clear localStorage / cookies in your browser to remove client-side preferences.  
- Operators can rotate API keys and delete server data for their instance.

## 7. Children

DevRadar is aimed at developers and is not directed at children under 13 (or the age required in your jurisdiction).

## 8. Changes

Updates will be committed to this file in the repository. Material changes should be reflected by updating the “Last updated” date.

## 9. Contact

Questions or deletion requests for a self-hosted instance: contact the operator of that instance.  
For the open-source project: https://github.com/bagusardin25/DevRadar/issues
