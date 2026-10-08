// The language chosen in SIP (stored by i18n.js), else the browser's.
const TEXT = {
  en: { page: "Sign in · SIP", title: "Log in", email: "Email address", password: "Password", submit: "Sign in", failed: "Incorrect email or password.", unreachable: "SIP cannot be reached. Try again in a moment." },
  nl: { page: "Inloggen · SIP", title: "Inloggen", email: "E-mailadres", password: "Wachtwoord", submit: "Inloggen", failed: "Onjuist e-mailadres of wachtwoord.", unreachable: "SIP is niet bereikbaar. Probeer het zo opnieuw." },
  de: { page: "Anmelden · SIP", title: "Anmelden", email: "E-Mail-Adresse", password: "Passwort", submit: "Anmelden", failed: "E-Mail-Adresse oder Passwort ist falsch.", unreachable: "SIP ist nicht erreichbar. Versuche es gleich noch einmal." },
};
let language = "en";
try { language = localStorage.getItem("sip_language") || ""; } catch {}
if (!TEXT[language]) language = (navigator.language || "en").slice(0, 2);
if (!TEXT[language]) language = "en";
const text = TEXT[language];
document.documentElement.lang = language;
document.title = text.page;
document.querySelectorAll("[data-text]").forEach((element) => { element.textContent = text[element.dataset.text]; });

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = document.querySelector("#submit");
  const error = document.querySelector("#error");
  button.disabled = true;
  error.textContent = "";
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-SIP-Language": language },
      body: JSON.stringify({
        email: document.querySelector("#email").value,
        password: document.querySelector("#password").value
      })
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : text.failed);
    }
    // Keep the language the user signed in with for the app itself.
    try { if (!localStorage.getItem("sip_language")) localStorage.setItem("sip_language", language); } catch {}
    window.location.replace("/");
  } catch (loginError) {
    error.textContent = loginError instanceof TypeError ? text.unreachable : loginError.message;
    button.disabled = false;
  }
});
