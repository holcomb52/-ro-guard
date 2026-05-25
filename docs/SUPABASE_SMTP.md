# Production SMTP for RO Shield (Supabase Auth)

RO Shield sends **password reset** and **invite** emails through **Supabase Auth**, not through the Streamlit app. Pick **one** sender provider below and configure custom SMTP in Supabase.

Supported in this guide:

- **Microsoft Outlook / Microsoft 365** (dealership domain — best for production)
- **Gmail / Google Workspace**
- **Yahoo Mail** (works for testing or small teams; less ideal as long-term production sender)

---

## Shared setup (all providers)

### Supabase → enable custom SMTP

1. [Supabase Dashboard](https://supabase.com/dashboard) → **ro-guard-db**  
2. **Authentication** → **Emails** → **Enable custom SMTP**  
3. Paste values from **one** provider section below  
4. **Save** → send a **test email** if offered  

### URL configuration (reset links)

**Authentication** → **URL Configuration**

| Setting | Local dev | Production (Streamlit Cloud) |
|---------|-----------|----------------------------|
| **Site URL** | `http://localhost:8531` | `https://ro-guard.streamlit.app` |
| **Redirect URLs** | `http://localhost:8531/**` | `https://ro-guard.streamlit.app/**` |

Add **both** if you develop locally and deploy to Streamlit.

### RO Shield app URL

**Local (`.env`):**

```bash
RO_SHIELD_APP_URL=http://localhost:8531
```

**Streamlit Cloud → Settings → Secrets:**

```toml
SUPABASE_URL = "https://eyufnhnabdgehkfvhqzf.supabase.co"
SUPABASE_KEY = "your_publishable_key_here"
RO_SHIELD_APP_URL = "https://ro-guard.streamlit.app"
```

### Email template (optional)

**Authentication** → **Emails** → **Templates** → **Reset password**

Example subject: `Reset your RO Shield password` — keep Supabase’s reset-link placeholder in the body.

### Test end-to-end

1. SMTP saved in Supabase  
2. Auth user exists (**Authentication** → **Users**) with the same email as Personnel  
3. RO Shield sign-in → **Forgot your password?**  
4. Check inbox and **spam / junk**  
5. Click link → **Set a new password** → sign in  

---

## Option A — Microsoft Outlook / Microsoft 365

Best for production when the dealership owns a domain (`warranty@yourdealership.com`).

### Mailbox setup

Create or use a dedicated mailbox, e.g. `warranty@yourdealership.com` — not a personal inbox long term.

**IT must enable SMTP for that mailbox:**

1. [Microsoft 365 admin center](https://admin.microsoft.com) → **Users** → **Active users** → select the mailbox  
2. **Mail** → **Manage email apps**  
3. Enable **Authenticated SMTP**  

### App password (when MFA is on)

1. [account.microsoft.com/security](https://account.microsoft.com/security) as the sender mailbox  
2. **Advanced security options** → **App passwords** → create (name: `Supabase RO Shield`)  
3. Use that password in Supabase — **not** the normal Outlook login password  

### Supabase SMTP values (Outlook)

| Supabase field | Value |
|----------------|--------|
| **Host** | `smtp.office365.com` |
| **Port** | `587` |
| **Username** | Full address, e.g. `warranty@yourdealership.com` |
| **Password** | Mailbox password or Microsoft **app password** |
| **Sender email** | Same as username |
| **Sender name** | `RO Shield` |

Use **`smtp.office365.com:587`** — not `smtp-mail.outlook.com`.

### Outlook troubleshooting

| Problem | Fix |
|---------|-----|
| SMTP authentication failed | Enable **Authenticated SMTP**; use **app password** if MFA is on |
| “535 5.7.3 Authentication unsuccessful” | SMTP AUTH disabled org-wide — IT must enable per mailbox |
| Mail never arrives | Check Junk; confirm mailbox is licensed M365 |

---

## Option B — Gmail / Google Workspace

Works with `@gmail.com` or Google Workspace (`you@dealership.com` if Google hosts your mail).

### App password (required for almost all accounts)

Google blocks normal passwords for SMTP from third-party apps. You need an **app password**:

1. Enable **2-Step Verification** on the Google account: [myaccount.google.com/security](https://myaccount.google.com/security)  
2. Open **App passwords**: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)  
3. Create an app password (app: **Mail**, device: **Other** → name `Supabase RO Shield`)  
4. Copy the 16-character password into Supabase SMTP **Password**  

**Google Workspace:** Admin may need to allow app passwords or SMTP relay under **Admin console** → **Apps** → **Google Workspace** → **Gmail** → **Routing** / security settings.

### Supabase SMTP values (Gmail)

| Supabase field | Value |
|----------------|--------|
| **Host** | `smtp.gmail.com` |
| **Port** | `587` |
| **Username** | Full address, e.g. `warranty@gmail.com` or `warranty@yourdealership.com` |
| **Password** | Google **app password** (not your normal Gmail password) |
| **Sender email** | Same as username |
| **Sender name** | `RO Shield` |

Use port **587** (STARTTLS). Avoid port 465 unless Supabase only offers SSL and 587 fails.

### Gmail troubleshooting

| Problem | Fix |
|---------|-----|
| “Username and Password not accepted” | Use an **app password**; 2-Step Verification must be ON |
| “Less secure app access” | Deprecated — app passwords are required |
| Workspace blocks SMTP | Ask Google admin to allow SMTP or app passwords for the sender account |
| Mail in spam | Expected for `@gmail.com` senders; use Workspace + dealership domain for production |

---

## Option C — Yahoo Mail

Works with `@yahoo.com`, `@yahoo.ca`, etc. Fine for testing or very small teams; Yahoo may rate-limit and is easier to flag as spam than a dealership domain.

### App password (required)

Yahoo requires an **app password** for third-party SMTP — your normal Yahoo login password will **not** work.

1. Sign in at [https://login.yahoo.com](https://login.yahoo.com)  
2. **Account info** → **Account security** (or [https://login.yahoo.com/account/security](https://login.yahoo.com/account/security))  
3. Enable **Two-step verification** if not already on  
4. **Generate app password** (or **Manage app passwords**)  
5. Name it `Supabase RO Shield` → copy the generated password  
6. Paste into Supabase SMTP **Password**  

### Supabase SMTP values (Yahoo)

| Supabase field | Value |
|----------------|--------|
| **Host** | `smtp.mail.yahoo.com` |
| **Port** | `587` |
| **Username** | Full Yahoo address, e.g. `user@yahoo.com` |
| **Password** | Yahoo **app password** (not your Yahoo login password) |
| **Sender email** | Same as username |
| **Sender name** | `RO Shield` |

Alternative if 587 fails in Supabase: port **465** with SSL (only if the dashboard supports it).

### Yahoo troubleshooting

| Problem | Fix |
|---------|-----|
| “Invalid credentials” / auth failed | Must use **app password**, not account password |
| No app password option | Turn on **two-step verification** first |
| Mail in spam | Common for Yahoo; ask users to check **Spam** folder |
| “Too many login attempts” | Wait 24h or generate a new app password |
| Sender looks personal | For production, prefer Outlook/Workspace on your dealership domain |

---

## Shared troubleshooting

| Problem | Fix |
|---------|-----|
| No email at all | Custom SMTP ON? Test email in Supabase? Check spam/junk |
| Reset link goes to localhost | Set `RO_SHIELD_APP_URL` in Streamlit Secrets to live URL |
| Link invalid / expired | Add app URL to Supabase **Redirect URLs**; request new reset link |
| User never gets mail | User must exist in **Authentication** → **Users** with that exact email |

---

## Checklist

**All providers**

- [ ] Custom SMTP enabled and saved in Supabase  
- [ ] Site URL + Redirect URLs configured  
- [ ] `RO_SHIELD_APP_URL` set (local `.env` and/or Streamlit Secrets)  
- [ ] Password reset tested from RO Shield sign-in  
- [ ] Personnel **Email (login)** matches Supabase Auth email  

**Outlook**

- [ ] Dedicated mailbox (e.g. `warranty@dealership.com`)  
- [ ] **Authenticated SMTP** enabled in M365 admin  

**Gmail**

- [ ] 2-Step Verification ON  
- [ ] **App password** created and used in Supabase  

**Yahoo**

- [ ] Two-step verification ON  
- [ ] **App password** created and used in Supabase  
