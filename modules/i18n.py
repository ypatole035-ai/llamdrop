"""
llamdrop - i18n.py
Multi-language UI strings.
Currently supports: English, Hindi, Spanish, Portuguese, Arabic.
Contributors: add your language by adding a new dict entry.
"""

import os
import json

LANGS = {
    "en": "English",
    "hi": "हिन्दी (Hindi)",
    "es": "Español (Spanish)",
    "pt": "Português (Portuguese)",
    "ar": "العربية (Arabic)",
}

# ── String tables ─────────────────────────────────────────────────────────────

STRINGS = {

    # ── English ───────────────────────────────────────────────────────────────
    "en": {
        "tagline":          "Run AI on any device. No PC. No subscription. No struggle.",
        "free_forever":     "Free forever · GPL v3",
        "loading":          "Loading llamdrop...",
        "menu_chat":        "Start chatting",
        "menu_browse":      "Browse & download",
        "menu_mymodels":    "My downloaded models",
        "menu_resume":      "Resume saved session",
        "menu_search":      "Search HuggingFace",
        "menu_device":      "Device info",
        "menu_help":        "Help",
        "menu_quit":        "Quit",
        "desc_chat":        "Pick a downloaded model and start",
        "desc_browse":      "Find models that work on your device",
        "desc_mymodels":    "See what you have installed",
        "desc_resume":      "Continue a previous conversation",
        "desc_search":      "Search all GGUF models on HuggingFace",
        "desc_device":      "See your hardware specs",
        "desc_help":        "How to use llamdrop",
        "no_models":        "No models downloaded yet.",
        "go_to_browse":     "Go to 'Browse & download' to get your first model.",
        "already_dl":       "Already downloaded. Go to 'Start chatting' to use it.",
        "dl_failed":        "Download failed",
        "dl_ready":         "Ready! Go to 'Start chatting' to use it.",
        "no_sessions":      "No saved sessions found.",
        "press_enter_back": "Press Enter to go back...",
        "save_session":     "Save this conversation? (y/N): ",
        "session_saved":    "Saved",
        "goodbye":          "Goodbye!",
        "chat_header":      "Chat",
        "chat_help_hint":   "Type /help for commands · Ctrl+C or /quit to exit",
        "cmd_save":         "/save   — save this conversation",
        "cmd_clear":        "/clear  — clear conversation history",
        "cmd_ram":          "/ram    — show current RAM usage",
        "cmd_quit":         "/quit   — exit chat",
        "context_trimmed":  "Context trimmed to free RAM",
        "ram_critical":     "CRITICAL RAM — Close other apps!",
        "ram_low":          "LOW RAM — Be careful",
        "ram_ok":           "RAM OK",
        "search_prompt":    "Search HuggingFace (e.g. 'qwen coding' or 'llama chat'): ",
        "searching":        "Searching HuggingFace...",
        "search_none":      "No compatible models found. Try a different search.",
        "unverified_warn":  "⚠ These results are unverified — RAM estimates only.",
        "update_catalog":   "Model catalog updated to",
        "update_app":       "New llamdrop version available",
        "llama_missing":    "llama.cpp not found. Run the installer first.",
        "nav_hint":         "↑↓ Navigate   Enter Select   Q Quit",
    },

    # ── Hindi ─────────────────────────────────────────────────────────────────
    "hi": {
        "tagline":          "किसी भी डिवाइस पर AI चलाएं। कोई PC नहीं। कोई सब्सक्रिप्शन नहीं।",
        "free_forever":     "हमेशा मुफ्त · GPL v3",
        "loading":          "llamdrop लोड हो रहा है...",
        "menu_chat":        "चैट शुरू करें",
        "menu_browse":      "मॉडल खोजें और डाउनलोड करें",
        "menu_mymodels":    "मेरे डाउनलोड किए गए मॉडल",
        "menu_resume":      "पिछली बातचीत फिर शुरू करें",
        "menu_search":      "HuggingFace पर खोजें",
        "menu_device":      "डिवाइस की जानकारी",
        "menu_help":        "सहायता",
        "menu_quit":        "बाहर निकलें",
        "desc_chat":        "डाउनलोड किया गया मॉडल चुनें और चैट करें",
        "desc_browse":      "आपके डिवाइस के लिए सही मॉडल खोजें",
        "desc_mymodels":    "देखें क्या इंस्टॉल है",
        "desc_resume":      "पिछली बातचीत जारी रखें",
        "desc_search":      "HuggingFace पर सभी GGUF मॉडल खोजें",
        "desc_device":      "अपने हार्डवेयर की जानकारी देखें",
        "desc_help":        "llamdrop कैसे उपयोग करें",
        "no_models":        "अभी कोई मॉडल डाउनलोड नहीं हुआ।",
        "go_to_browse":     "पहला मॉडल पाने के लिए 'मॉडल खोजें' पर जाएं।",
        "already_dl":       "पहले से डाउनलोड है। 'चैट शुरू करें' पर जाएं।",
        "dl_failed":        "डाउनलोड विफल",
        "dl_ready":         "तैयार! 'चैट शुरू करें' पर जाएं।",
        "no_sessions":      "कोई सहेजी गई बातचीत नहीं मिली।",
        "press_enter_back": "वापस जाने के लिए Enter दबाएं...",
        "save_session":     "यह बातचीत सहेजें? (y/N): ",
        "session_saved":    "सहेजा गया",
        "goodbye":          "अलविदा!",
        "chat_header":      "चैट",
        "chat_help_hint":   "/help टाइप करें · बाहर निकलने के लिए /quit",
        "cmd_save":         "/save   — बातचीत सहेजें",
        "cmd_clear":        "/clear  — बातचीत साफ करें",
        "cmd_ram":          "/ram    — RAM देखें",
        "cmd_quit":         "/quit   — चैट बंद करें",
        "context_trimmed":  "RAM खाली करने के लिए पुराना संदर्भ हटाया",
        "ram_critical":     "RAM बहुत कम है — अन्य ऐप बंद करें!",
        "ram_low":          "RAM कम है — सावधान रहें",
        "ram_ok":           "RAM ठीक है",
        "search_prompt":    "HuggingFace पर खोजें (जैसे 'qwen hindi' या 'llama chat'): ",
        "searching":        "HuggingFace पर खोज रहे हैं...",
        "search_none":      "कोई संगत मॉडल नहीं मिला। कुछ और खोजें।",
        "unverified_warn":  "⚠ ये परिणाम असत्यापित हैं — RAM अनुमान मात्र।",
        "update_catalog":   "मॉडल सूची अपडेट हुई",
        "update_app":       "llamdrop का नया संस्करण उपलब्ध है",
        "llama_missing":    "llama.cpp नहीं मिला। पहले installer चलाएं।",
        "nav_hint":         "↑↓ नेविगेट करें   Enter चुनें   Q बाहर निकलें",
    },

    # ── Spanish ───────────────────────────────────────────────────────────────
    "es": {
        "tagline":          "Ejecuta IA en cualquier dispositivo. Sin PC. Sin suscripción.",
        "free_forever":     "Gratis para siempre · GPL v3",
        "loading":          "Cargando llamdrop...",
        "menu_chat":        "Iniciar chat",
        "menu_browse":      "Explorar y descargar",
        "menu_mymodels":    "Mis modelos descargados",
        "menu_resume":      "Reanudar sesión guardada",
        "menu_search":      "Buscar en HuggingFace",
        "menu_device":      "Info del dispositivo",
        "menu_help":        "Ayuda",
        "menu_quit":        "Salir",
        "desc_chat":        "Elige un modelo descargado y empieza",
        "desc_browse":      "Encuentra modelos para tu dispositivo",
        "desc_mymodels":    "Ve lo que tienes instalado",
        "desc_resume":      "Continúa una conversación anterior",
        "desc_search":      "Busca todos los modelos GGUF en HuggingFace",
        "desc_device":      "Ve las especificaciones de tu hardware",
        "desc_help":        "Cómo usar llamdrop",
        "no_models":        "Aún no hay modelos descargados.",
        "go_to_browse":     "Ve a 'Explorar y descargar' para tu primer modelo.",
        "already_dl":       "Ya descargado. Ve a 'Iniciar chat' para usarlo.",
        "dl_failed":        "Descarga fallida",
        "dl_ready":         "¡Listo! Ve a 'Iniciar chat' para usarlo.",
        "no_sessions":      "No se encontraron sesiones guardadas.",
        "press_enter_back": "Presiona Enter para volver...",
        "save_session":     "¿Guardar esta conversación? (y/N): ",
        "session_saved":    "Guardado",
        "goodbye":          "¡Adiós!",
        "chat_header":      "Chat",
        "chat_help_hint":   "Escribe /help para comandos · Ctrl+C o /quit para salir",
        "cmd_save":         "/save   — guardar conversación",
        "cmd_clear":        "/clear  — borrar historial",
        "cmd_ram":          "/ram    — ver uso de RAM",
        "cmd_quit":         "/quit   — salir del chat",
        "context_trimmed":  "Contexto reducido para liberar RAM",
        "ram_critical":     "RAM CRÍTICA — ¡Cierra otras apps!",
        "ram_low":          "RAM BAJA — Ten cuidado",
        "ram_ok":           "RAM OK",
        "search_prompt":    "Buscar en HuggingFace (ej. 'llama chat' o 'qwen codigo'): ",
        "searching":        "Buscando en HuggingFace...",
        "search_none":      "No se encontraron modelos compatibles. Prueba otra búsqueda.",
        "unverified_warn":  "⚠ Estos resultados no están verificados — solo estimaciones de RAM.",
        "update_catalog":   "Catálogo de modelos actualizado a",
        "update_app":       "Nueva versión de llamdrop disponible",
        "llama_missing":    "llama.cpp no encontrado. Ejecuta el instalador primero.",
        "nav_hint":         "↑↓ Navegar   Enter Seleccionar   Q Salir",
    },

    # ── Portuguese ────────────────────────────────────────────────────────────
    "pt": {
        "tagline":          "Execute IA em qualquer dispositivo. Sem PC. Sem assinatura.",
        "free_forever":     "Sempre grátis · GPL v3",
        "loading":          "Carregando llamdrop...",
        "menu_chat":        "Iniciar chat",
        "menu_browse":      "Explorar e baixar",
        "menu_mymodels":    "Meus modelos baixados",
        "menu_resume":      "Retomar sessão salva",
        "menu_search":      "Pesquisar no HuggingFace",
        "menu_device":      "Info do dispositivo",
        "menu_help":        "Ajuda",
        "menu_quit":        "Sair",
        "desc_chat":        "Escolha um modelo baixado e comece",
        "desc_browse":      "Encontre modelos para o seu dispositivo",
        "desc_mymodels":    "Veja o que você tem instalado",
        "desc_resume":      "Continue uma conversa anterior",
        "desc_search":      "Pesquise todos os modelos GGUF no HuggingFace",
        "desc_device":      "Veja as especificações do seu hardware",
        "desc_help":        "Como usar o llamdrop",
        "no_models":        "Nenhum modelo baixado ainda.",
        "go_to_browse":     "Vá em 'Explorar e baixar' para seu primeiro modelo.",
        "already_dl":       "Já baixado. Vá em 'Iniciar chat' para usar.",
        "dl_failed":        "Download falhou",
        "dl_ready":         "Pronto! Vá em 'Iniciar chat' para usar.",
        "no_sessions":      "Nenhuma sessão salva encontrada.",
        "press_enter_back": "Pressione Enter para voltar...",
        "save_session":     "Salvar esta conversa? (y/N): ",
        "session_saved":    "Salvo",
        "goodbye":          "Tchau!",
        "chat_header":      "Chat",
        "chat_help_hint":   "Digite /help para comandos · Ctrl+C ou /quit para sair",
        "cmd_save":         "/save   — salvar conversa",
        "cmd_clear":        "/clear  — limpar histórico",
        "cmd_ram":          "/ram    — ver uso de RAM",
        "cmd_quit":         "/quit   — sair do chat",
        "context_trimmed":  "Contexto reduzido para liberar RAM",
        "ram_critical":     "RAM CRÍTICA — Feche outros apps!",
        "ram_low":          "RAM BAIXA — Cuidado",
        "ram_ok":           "RAM OK",
        "search_prompt":    "Pesquisar no HuggingFace (ex. 'llama chat' ou 'qwen codigo'): ",
        "searching":        "Pesquisando no HuggingFace...",
        "search_none":      "Nenhum modelo compatível encontrado. Tente outra pesquisa.",
        "unverified_warn":  "⚠ Estes resultados não são verificados — apenas estimativas de RAM.",
        "update_catalog":   "Catálogo de modelos atualizado para",
        "update_app":       "Nova versão do llamdrop disponível",
        "llama_missing":    "llama.cpp não encontrado. Execute o instalador primeiro.",
        "nav_hint":         "↑↓ Navegar   Enter Selecionar   Q Sair",
    },
}

# ── Language management ───────────────────────────────────────────────────────

LANG_FILE = os.path.join(os.path.expanduser("~/.llamdrop"), "lang.txt")
_current_lang = "en"


def load_language():
    """Load saved language preference, default to English."""
    global _current_lang
    try:
        with open(LANG_FILE) as f:
            lang = f.read().strip()
        if lang in STRINGS:
            _current_lang = lang
    except Exception:
        _current_lang = "en"
    return _current_lang


def save_language(lang_code):
    """Save language preference."""
    global _current_lang
    if lang_code in STRINGS:
        _current_lang = lang_code
        try:
            os.makedirs(os.path.dirname(LANG_FILE), exist_ok=True)
            with open(LANG_FILE, "w") as f:
                f.write(lang_code)
        except Exception:
            pass


def t(key):
    """
    Translate a string key to the current language.
    Falls back to English if key not found in current language.
    """
    lang_strings = STRINGS.get(_current_lang, STRINGS["en"])
    return lang_strings.get(key) or STRINGS["en"].get(key, key)


def get_current_lang():
    return _current_lang


def get_available_langs():
    return LANGS


def choose_language_menu():
    """
    Simple numbered language chooser.
    Returns the selected language code.
    """
    print("\n  Choose your language / अपनी भाषा चुनें:\n")
    lang_list = list(LANGS.items())
    for i, (code, name) in enumerate(lang_list):
        print(f"  [{i+1}] {name}")

    print("")
    try:
        choice = int(input("  Enter number: ").strip())
        if 1 <= choice <= len(lang_list):
            code = lang_list[choice - 1][0]
            save_language(code)
            return code
    except (ValueError, EOFError):
        pass

    return "en"
