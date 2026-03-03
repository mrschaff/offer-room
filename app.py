import streamlit as st
import anthropic
import json
import io
import os
import re
import uuid
import time
import tempfile
import urllib.parse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

try:
    import stripe as _stripe_lib
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

load_dotenv()

# Dev mode is read from env only (safe at module level, no st.* calls)
_DEV_MODE = os.environ.get("DEV_MODE", "").lower() in ("true", "1", "yes")


# ── Secrets helper ─────────────────────────────────────────────────────────────

def _s(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        try:
            val = st.secrets.get(key, "")
        except Exception:
            pass
    return val or ""


# ── i18n ───────────────────────────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict] = {
    "en": {
        # Gate page
        "gate_create": "📝 Create account",
        "gate_login": "🔓 Log in",
        "gate_new": "New to OfferRoom?",
        "gate_new_desc": "Create a free account to get started. Buy interview credits to use the app.",
        "gate_existing": "Already have an account?",
        "gate_existing_desc": "Log in to access your interviews and purchase interview credits.",
        # Auth
        "auth_login": "Log in",
        "auth_signup": "Sign up",
        "auth_email_lbl": "Email",
        "auth_email_ph": "you@example.com",
        "auth_password_lbl": "Password",
        "auth_password_ph": "Min. 8 characters",
        "auth_confirm_lbl": "Confirm password",
        "auth_confirm_ph": "Re-enter password",
        "auth_login_btn": "Log in →",
        "auth_signup_btn": "Create account →",
        "auth_back": "← Back",
        "auth_logout": "Log out",
        "auth_err_email": "Please enter a valid email.",
        "auth_err_password_short": "Password must be at least 8 characters.",
        "auth_err_password_match": "Passwords don't match.",
        "auth_err_email_taken": "This email is already registered.",
        "auth_err_invalid": "Incorrect email or password.",
        "auth_err_unknown": "Something went wrong. Please try again.",
        "auth_err_no_firebase": "Authentication is not configured.",
        # Account bar
        "acct_change": "Change",
        "acct_history": "History",
        "acct_logout_btn": "Log out",
        "acct_credits": "{n} interviews left",
        # Main app (setup)
        "subtitle": "Prep for any interview, any job, any level, with any interviewer.",
        "lbl_cv": "Your CV",
        "lbl_role": "Role title",
        "lbl_seniority": "Seniority",
        "lbl_company": "Company",
        "lbl_jd": "Job description",
        "lbl_jd_optional": "optional",
        "lbl_interviewer": "Interviewer",
        "lbl_difficulty": "Difficulty",
        "ph_role": "e.g. Senior Product Manager",
        "ph_company_url": "https://company.com  (optional — we'll read it for you)",
        "ph_company_text": "Brief description of the company, product, and industry…",
        "ph_jd": "Paste the job description for a more accurate match score…",
        "btn_evaluate": "Evaluate →",
        "btn_match": "Match CV ↔ Role",
        "btn_start": "Start Interview →",
        "btn_back": "← Back",
        "btn_back_help": "Return to setup (progress will be lost)",
        "btn_start_over": "Start Over",
        "btn_get_eval": "Get My Evaluation →",
        "spin_cv": "Reading your CV…",
        "spin_company": "Fetching and summarising company website…",
        "spin_match": "Scoring your match…",
        "spin_interview": "Your interviewer is preparing…",
        "spin_eval": "Analysing your performance…",
        "enable_hint": "To enable: {parts}.",
        "enable_cv": "upload your CV",
        "enable_role": "add a role title",
        "err_cv": "Could not analyse CV: {e}",
        "err_cv_no_access": "You need at least 1 interview credit to analyze your CV. Buy credits to get started.",
        "err_start": "Could not start interview: {e}",
        "err_match": "Could not score match: {e}",
        "err_eval": "Could not generate evaluation: {e}",
        "interview_complete": "Interview complete.",
        "match_1": "No match",
        "match_2": "Distant match",
        "match_3": "Average match",
        "match_4": "Good match",
        "match_5": "Perfect match",
        "progress_done": "Interview complete",
        "progress_q": "Question {n} of {total}",
        "q_label": "**Question {n} of {total}:**",
        "chat_placeholder": "Your answer…",
        "diff_Friendly": "Friendly",
        "diff_Realistic": "Realistic",
        "diff_Brutal": "Brutal",
        # Payment
        "buy_title": "Buy more interviews",
        "sidebar_buy_1": "1 interview — $0.59",
        "sidebar_buy_5": "5 interviews — $1.49",
        "sidebar_buy_50": "50 interviews — $9.99",
        "sidebar_pay_now": "Go to payment →",
        "sidebar_pay_cancel": "Cancel",
        "payment_success": "✅ {n} interview(s) added!",
        "payment_error": "❌ Could not verify payment: {e}",
        "payment_cancelled": "Payment cancelled.",
        "no_credits": "You have 0 interviews left. Buy more to start.",
        "confirm_interview_cost": "This will use 1 of your {n} interview(s). You'll have {after} left.",
        "post_eval_used": "Interview done. {n} interview(s) remaining.",
        "post_eval_low": "Running low — buy more interviews to keep practising.",
        "err_out_of_interviews": "❌ Out of interviews",
        "err_out_of_interviews_msg": "You've used all your available interviews.",
        "buy_more_btn": "Buy more interviews →",
        # History
        "history_title": "Interview History",
        "history_back": "← Back to app",
        "history_no_interviews": "No interviews yet. Complete your first to see your history here.",
        "history_total": "Total sessions",
        "history_avg": "Avg score",
        "history_best": "Best score",
        "history_loading": "Loading history…",
        # CV storage
        "cv_choose": "Choose a CV",
        "cv_upload_new": "↑ Upload new CV",
        "cv_saved_ok": "✓ CV saved.",
        "cv_cached_ok": "⚡ Loaded from cache",
        "cv_delete": "Delete",
        "cv_limit_warn": "You have 5 saved CVs (max). Delete one to upload a new one.",
        # Voice input
        "voice_toggle_mic": "Switch to voice input",
        "voice_toggle_text": "Switch to text input",
        "voice_unavailable": "Voice input could not load. Please type your answer.",
        # Claude instructions
        "lang_instruction": (
            "LANGUAGE RULE: Conduct the entire interview in English. "
            "All questions, follow-ups, and responses must be in English."
        ),
        "eval_lang_instruction": (
            "Write the evaluation in English. "
            "IMPORTANT: The score line must always start with exactly 'FINAL SCORE: X.X / 5' "
            "— never change this specific string format."
        ),
        # Custom interviewer
        "custom_role_title": "Custom Interviewer",
        "custom_role_ph": "e.g. Librarian, Data Analyst, Sales Manager",
        "custom_role_context": "Additional context (optional)",
        "custom_role_context_ph": "Paste your background, job description, or any context for the interviewer…",
        "custom_role_confirmed": "✓ Custom interviewer ready",
        "custom_role_edit": "Change",
        "custom_role_placeholder": "Describe the role you're interviewing for…",
        # Share results
        "share_title": "Share your result",
        "share_card_title": "Tell your friends about your score:",
        "share_role": "Role",
        "share_interviewer": "Interviewer",
        "share_score": "Score",
        "share_twitter": "𝕏 Tweet",
        "share_linkedin": "in LinkedIn",
        "share_whatsapp": "💬 WhatsApp",
        "share_copy": "📋 Copy",
        "share_caption": "Sharing helps your network discover OfferRoom and prepares them for interviews too!",
        "share_message": "I just completed an interview prep with OfferRoom! 🎤 Role: {role} | Interviewer: {interviewer} | Difficulty: {difficulty} | Score: {score}/5 | Ready to ace your next interview? Try OfferRoom free at offerroom.com",
        # Post-interview stats
        "stats_performance": "Your Performance",
        "stats_strength": "Your strength",
        "stats_weakness": "Work on",
        "stats_narrative": "Communication",
        "stats_technical": "Technical Knowledge",
        "stats_logical": "Problem Solving",
        # Difficulty descriptions
        "difficulty_friendly_desc": "Supportive interviewer. Questions are clear and well-structured. Low pressure environment to test your thinking naturally.",
        "difficulty_realistic_desc": "Professional interviewer. Time-conscious with probing follow-ups. Expects specific examples and metrics. This mirrors real interviews.",
        "difficulty_brutal_desc": "Demanding interviewer. Will stress-test your thinking with edge cases. Expects deep reasoning and won't accept vague answers.",
        # Interview UX
        "interview_timer": "Interview time",
        "interview_practice_again": "Practice this role again",
        "interview_try_different": "Try different role",
        "interview_incomplete_warning": "Interview in progress",
        "interview_resume": "Resume interview",
        "interview_abandon": "Abandon and go back",
        "interview_incomplete_desc": "You have an interview in progress. Going back will abandon it.",
        # Dev mode
        "dev_badge": "🛠 DEV MODE",
    },
    "es": {
        "gate_create": "📝 Crear cuenta",
        "gate_login": "🔓 Iniciar sesión",
        "gate_new": "¿Nuevo en OfferRoom?",
        "gate_new_desc": "Crea una cuenta gratuita para empezar. Compra créditos de entrevista para usar la app.",
        "gate_existing": "¿Ya tienes una cuenta?",
        "gate_existing_desc": "Inicia sesión para acceder a tus entrevistas y comprar créditos de entrevista.",
        "auth_login": "Iniciar sesión",
        "auth_signup": "Registrarse",
        "auth_email_lbl": "Email",
        "auth_email_ph": "tu@email.com",
        "auth_password_lbl": "Contraseña",
        "auth_password_ph": "Mín. 8 caracteres",
        "auth_confirm_lbl": "Confirmar contraseña",
        "auth_confirm_ph": "Repite la contraseña",
        "auth_login_btn": "Iniciar sesión →",
        "auth_signup_btn": "Crear cuenta →",
        "auth_back": "← Volver",
        "auth_logout": "Cerrar sesión",
        "auth_err_email": "Introduce un email válido.",
        "auth_err_password_short": "La contraseña debe tener al menos 8 caracteres.",
        "auth_err_password_match": "Las contraseñas no coinciden.",
        "auth_err_email_taken": "Este email ya está registrado.",
        "auth_err_invalid": "Email o contraseña incorrectos.",
        "auth_err_unknown": "Algo salió mal. Inténtalo de nuevo.",
        "auth_err_no_firebase": "La autenticación no está configurada.",
        "acct_change": "Cambiar",
        "acct_history": "Hist.",
        "acct_logout_btn": "Salir",
        "acct_credits": "{n} entrevistas restantes",
        "subtitle": "Prepárate para cualquier entrevista, cualquier puesto, cualquier nivel.",
        "lbl_cv": "Tu CV",
        "lbl_role": "Título del puesto",
        "lbl_seniority": "Nivel",
        "lbl_company": "Empresa",
        "lbl_jd": "Descripción del puesto",
        "lbl_jd_optional": "opcional",
        "lbl_interviewer": "Entrevistador",
        "lbl_difficulty": "Dificultad",
        "ph_role": "ej. Senior Product Manager",
        "ph_company_url": "https://empresa.com  (opcional — lo leeremos por ti)",
        "ph_company_text": "Breve descripción de la empresa, producto e industria…",
        "ph_jd": "Pega la descripción del puesto para una puntuación más precisa…",
        "btn_evaluate": "Evaluar →",
        "btn_match": "Comparar CV ↔ Puesto",
        "btn_start": "Iniciar entrevista →",
        "btn_back": "← Volver",
        "btn_back_help": "Volver a la configuración (se perderá el progreso)",
        "btn_start_over": "Empezar de nuevo",
        "btn_get_eval": "Ver mi evaluación →",
        "spin_cv": "Leyendo tu CV…",
        "spin_company": "Obteniendo y resumiendo el sitio web de la empresa…",
        "spin_match": "Calculando tu compatibilidad…",
        "spin_interview": "Tu entrevistador está preparándose…",
        "spin_eval": "Analizando tu rendimiento…",
        "enable_hint": "Para habilitar: {parts}.",
        "enable_cv": "sube tu CV",
        "enable_role": "añade un título de puesto",
        "err_cv": "No se pudo analizar el CV: {e}",
        "err_cv_no_access": "Necesitas al menos 1 crédito de entrevista para analizar tu CV. Compra créditos para comenzar.",
        "err_start": "No se pudo iniciar la entrevista: {e}",
        "err_match": "No se pudo calcular la compatibilidad: {e}",
        "err_eval": "No se pudo generar la evaluación: {e}",
        "interview_complete": "Entrevista completada.",
        "match_1": "Sin compatibilidad",
        "match_2": "Compatibilidad baja",
        "match_3": "Compatibilidad media",
        "match_4": "Buena compatibilidad",
        "match_5": "Compatibilidad perfecta",
        "progress_done": "Entrevista completada",
        "progress_q": "Pregunta {n} de {total}",
        "q_label": "**Pregunta {n} de {total}:**",
        "chat_placeholder": "Tu respuesta…",
        "diff_Friendly": "Amigable",
        "diff_Realistic": "Realista",
        "diff_Brutal": "Brutal",
        "buy_title": "Comprar más entrevistas",
        "sidebar_buy_1": "1 entrevista — $0.59",
        "sidebar_buy_5": "5 entrevistas — $1.49",
        "sidebar_buy_50": "50 entrevistas — $9.99",
        "sidebar_pay_now": "Ir al pago →",
        "sidebar_pay_cancel": "Cancelar",
        "payment_success": "✅ ¡{n} entrevista(s) añadida(s)!",
        "payment_error": "❌ No se pudo verificar el pago: {e}",
        "payment_cancelled": "Pago cancelado.",
        "no_credits": "Tienes 0 entrevistas restantes. Compra más para comenzar.",
        "confirm_interview_cost": "Esto usará 1 de tus {n} entrevista(s). Te quedarán {after}.",
        "post_eval_used": "Entrevista completada. {n} entrevista(s) restantes.",
        "post_eval_low": "¡Casi sin entrevistas! Compra más para seguir practicando.",
        "err_out_of_interviews": "❌ Sin entrevistas",
        "err_out_of_interviews_msg": "Has usado todas tus entrevistas disponibles.",
        "buy_more_btn": "Comprar más entrevistas →",
        "history_title": "Historial de entrevistas",
        "history_back": "← Volver a la app",
        "history_no_interviews": "Aún no hay entrevistas. Completa tu primera para ver tu historial.",
        "history_total": "Total",
        "history_avg": "Puntuación media",
        "history_best": "Mejor puntuación",
        "history_loading": "Cargando historial…",
        # CV storage
        "cv_choose": "Elige un CV",
        "cv_upload_new": "↑ Subir nuevo CV",
        "cv_saved_ok": "✓ CV guardado.",
        "cv_cached_ok": "⚡ Cargado del caché",
        "cv_delete": "Eliminar",
        "cv_limit_warn": "Tienes 5 CVs guardados (máx.). Elimina uno para subir uno nuevo.",
        # Voice input
        "voice_toggle_mic": "Cambiar a entrada de voz",
        "voice_toggle_text": "Cambiar a entrada de texto",
        "voice_unavailable": "La entrada de voz no pudo cargarse. Por favor escribe tu respuesta.",
        "lang_instruction": (
            "REGLA DE IDIOMA: Realiza toda la entrevista íntegramente en español. "
            "Todas las preguntas, seguimientos y respuestas deben estar en español."
        ),
        "eval_lang_instruction": (
            "Escribe la evaluación íntegramente en español. "
            "IMPORTANTE: La línea de puntuación debe comenzar siempre con exactamente "
            "'FINAL SCORE: X.X / 5' — no cambies nunca este formato específico."
        ),
        # Custom interviewer
        "custom_role_title": "Entrevistador personalizado",
        "custom_role_ph": "ej. Bibliotecario, Analista de datos, Gerente de ventas",
        "custom_role_context": "Contexto adicional (opcional)",
        "custom_role_context_ph": "Pega tu perfil, descripción del puesto o cualquier contexto para el entrevistador…",
        "custom_role_confirmed": "✓ Entrevistador personalizado listo",
        "custom_role_edit": "Cambiar",
        "custom_role_placeholder": "Describe el rol para el que te estás entrevistando…",
        # Share results
        "share_title": "Comparte tu resultado",
        "share_card_title": "Cuéntale a tus amigos sobre tu puntuación:",
        "share_role": "Puesto",
        "share_interviewer": "Entrevistador",
        "share_score": "Puntuación",
        "share_twitter": "𝕏 Tweet",
        "share_linkedin": "in LinkedIn",
        "share_whatsapp": "💬 WhatsApp",
        "share_copy": "📋 Copiar",
        "share_caption": "¡Compartir ayuda a tu red a descubrir OfferRoom y prepararse para entrevistas!",
        "share_message": "¡Acabo de completar una preparación de entrevista con OfferRoom! 🎤 Puesto: {role} | Entrevistador: {interviewer} | Dificultad: {difficulty} | Puntuación: {score}/5 | ¿Listo para brillar en tu próxima entrevista? Prueba OfferRoom gratis en offerroom.com",
        # Post-interview stats
        "stats_performance": "Tu rendimiento",
        "stats_strength": "Tu fortaleza",
        "stats_weakness": "Trabaja en",
        "stats_narrative": "Comunicación",
        "stats_technical": "Conocimiento técnico",
        "stats_logical": "Resolución de problemas",
        # Difficulty descriptions
        "difficulty_friendly_desc": "Entrevistador de apoyo. Las preguntas son claras y bien estructuradas. Ambiente de baja presión.",
        "difficulty_realistic_desc": "Entrevistador profesional. Consciente del tiempo con seguimientos profundos. Espera ejemplos específicos y métricas.",
        "difficulty_brutal_desc": "Entrevistador exigente. Pondrá a prueba tu pensamiento con casos extremos. Espera razonamientos profundos.",
        # Interview UX
        "interview_timer": "Tiempo de entrevista",
        "interview_practice_again": "Practicar este rol de nuevo",
        "interview_try_different": "Intentar rol diferente",
        "interview_incomplete_warning": "Entrevista en progreso",
        "interview_resume": "Reanudar entrevista",
        "interview_abandon": "Abandonar y volver",
        "interview_incomplete_desc": "Tienes una entrevista en progreso. Volver la abandonará.",
        "dev_badge": "🛠 MODO DEV",
    },
    "pt": {
        "gate_create": "📝 Criar conta",
        "gate_login": "🔓 Entrar",
        "gate_new": "Novo no OfferRoom?",
        "gate_new_desc": "Crie uma conta gratuita para começar. Compre créditos de entrevista para usar o aplicativo.",
        "gate_existing": "Já tem uma conta?",
        "gate_existing_desc": "Faça login para acessar suas entrevistas e comprar créditos de entrevista.",
        "auth_login": "Entrar",
        "auth_signup": "Criar conta",
        "auth_email_lbl": "E-mail",
        "auth_email_ph": "voce@email.com",
        "auth_password_lbl": "Senha",
        "auth_password_ph": "Mín. 8 caracteres",
        "auth_confirm_lbl": "Confirmar senha",
        "auth_confirm_ph": "Re-insira a senha",
        "auth_login_btn": "Entrar →",
        "auth_signup_btn": "Criar conta →",
        "auth_back": "← Voltar",
        "auth_logout": "Sair",
        "auth_err_email": "Digite um e-mail válido.",
        "auth_err_password_short": "A senha deve ter pelo menos 8 caracteres.",
        "auth_err_password_match": "As senhas não coincidem.",
        "auth_err_email_taken": "Este e-mail já está registrado.",
        "auth_err_invalid": "E-mail ou senha incorretos.",
        "auth_err_unknown": "Algo deu errado. Tente novamente.",
        "auth_err_no_firebase": "A autenticação não está configurada.",
        "acct_change": "Alterar",
        "acct_history": "Hist.",
        "acct_logout_btn": "Sair",
        "acct_credits": "{n} entrevistas restantes",
        "subtitle": "Prepare-se para qualquer entrevista, qualquer vaga, qualquer nível.",
        "lbl_cv": "Seu CV",
        "lbl_role": "Título do cargo",
        "lbl_seniority": "Senioridade",
        "lbl_company": "Empresa",
        "lbl_jd": "Descrição da vaga",
        "lbl_jd_optional": "opcional",
        "lbl_interviewer": "Entrevistador",
        "lbl_difficulty": "Dificuldade",
        "ph_role": "ex. Gerente de Produto Sênior",
        "ph_company_url": "https://empresa.com  (opcional — vamos ler para você)",
        "ph_company_text": "Breve descrição da empresa, produto e setor…",
        "ph_jd": "Cole a descrição da vaga para uma pontuação mais precisa…",
        "btn_evaluate": "Avaliar →",
        "btn_match": "Comparar CV ↔ Vaga",
        "btn_start": "Iniciar entrevista →",
        "btn_back": "← Voltar",
        "btn_back_help": "Voltar à configuração (o progresso será perdido)",
        "btn_start_over": "Recomeçar",
        "btn_get_eval": "Ver minha avaliação →",
        "spin_cv": "Lendo seu CV…",
        "spin_company": "Buscando e resumindo o site da empresa…",
        "spin_match": "Calculando sua compatibilidade…",
        "spin_interview": "Seu entrevistador está se preparando…",
        "spin_eval": "Analisando seu desempenho…",
        "enable_hint": "Para habilitar: {parts}.",
        "enable_cv": "faça upload do seu CV",
        "enable_role": "adicione um título de cargo",
        "err_cv": "Não foi possível analisar o CV: {e}",
        "err_cv_no_access": "Você precisa de pelo menos 1 crédito de entrevista para analisar seu CV. Compre créditos para começar.",
        "err_start": "Não foi possível iniciar a entrevista: {e}",
        "err_match": "Não foi possível calcular a compatibilidade: {e}",
        "err_eval": "Não foi possível gerar a avaliação: {e}",
        "interview_complete": "Entrevista concluída.",
        "match_1": "Sem compatibilidade",
        "match_2": "Compatibilidade baixa",
        "match_3": "Compatibilidade média",
        "match_4": "Boa compatibilidade",
        "match_5": "Compatibilidade perfeita",
        "progress_done": "Entrevista concluída",
        "progress_q": "Pergunta {n} de {total}",
        "q_label": "**Pergunta {n} de {total}:**",
        "chat_placeholder": "Sua resposta…",
        "diff_Friendly": "Amigável",
        "diff_Realistic": "Realista",
        "diff_Brutal": "Brutal",
        "buy_title": "Comprar mais entrevistas",
        "sidebar_buy_1": "1 entrevista — $0.59",
        "sidebar_buy_5": "5 entrevistas — $1.49",
        "sidebar_buy_50": "50 entrevistas — $9.99",
        "sidebar_pay_now": "Ir para pagamento →",
        "sidebar_pay_cancel": "Cancelar",
        "payment_success": "✅ {n} entrevista(s) adicionada(s)!",
        "payment_error": "❌ Não foi possível verificar o pagamento: {e}",
        "payment_cancelled": "Pagamento cancelado.",
        "no_credits": "Você tem 0 entrevistas restantes. Compre mais para começar.",
        "confirm_interview_cost": "Isso usará 1 das suas {n} entrevista(s). Restarão {after}.",
        "post_eval_used": "Entrevista concluída. {n} entrevista(s) restante(s).",
        "post_eval_low": "Quase sem entrevistas! Compre mais para continuar praticando.",
        "err_out_of_interviews": "❌ Sem entrevistas",
        "err_out_of_interviews_msg": "Você usou todas as suas entrevistas disponíveis.",
        "buy_more_btn": "Comprar mais entrevistas →",
        "history_title": "Histórico de entrevistas",
        "history_back": "← Voltar ao app",
        "history_no_interviews": "Ainda sem entrevistas. Complete a primeira para ver seu histórico.",
        "history_total": "Total",
        "history_avg": "Pontuação média",
        "history_best": "Melhor pontuação",
        "history_loading": "Carregando histórico…",
        # CV storage
        "cv_choose": "Escolha um CV",
        "cv_upload_new": "↑ Enviar novo CV",
        "cv_saved_ok": "✓ CV salvo.",
        "cv_cached_ok": "⚡ Carregado do cache",
        "cv_delete": "Excluir",
        "cv_limit_warn": "Você tem 5 CVs salvos (máx.). Exclua um para enviar um novo.",
        # Voice input
        "voice_toggle_mic": "Mudar para entrada de voz",
        "voice_toggle_text": "Mudar para entrada de texto",
        "voice_unavailable": "A entrada de voz não pôde carregar. Por favor digite sua resposta.",
        "lang_instruction": (
            "REGRA DE IDIOMA: Conduza toda a entrevista inteiramente em português brasileiro. "
            "Todas as perguntas, acompanhamentos e respostas devem estar em português brasileiro."
        ),
        "eval_lang_instruction": (
            "Escreva a avaliação inteiramente em português brasileiro. "
            "IMPORTANTE: A linha de pontuação deve sempre começar exatamente com "
            "'FINAL SCORE: X.X / 5' — nunca altere este formato específico."
        ),
        # Custom interviewer
        "custom_role_title": "Entrevistador personalizado",
        "custom_role_ph": "ex. Bibliotecário, Analista de dados, Gerente de vendas",
        "custom_role_context": "Contexto adicional (opcional)",
        "custom_role_context_ph": "Cole seu perfil, descrição da vaga ou qualquer contexto para o entrevistador…",
        "custom_role_confirmed": "✓ Entrevistador personalizado pronto",
        "custom_role_edit": "Alterar",
        "custom_role_placeholder": "Descreva o cargo para o qual está se entrevistando…",
        # Share results
        "share_title": "Compartilhe seu resultado",
        "share_card_title": "Conte aos seus amigos sobre sua pontuação:",
        "share_role": "Cargo",
        "share_interviewer": "Entrevistador",
        "share_score": "Pontuação",
        "share_twitter": "𝕏 Tweet",
        "share_linkedin": "in LinkedIn",
        "share_whatsapp": "💬 WhatsApp",
        "share_copy": "📋 Copiar",
        "share_caption": "Compartilhar ajuda sua rede a descobrir OfferRoom e se preparar para entrevistas!",
        "share_message": "Acabei de completar uma preparação de entrevista com OfferRoom! 🎤 Cargo: {role} | Entrevistador: {interviewer} | Dificuldade: {difficulty} | Pontuação: {score}/5 | Pronto para mandar bem na próxima entrevista? Experimente OfferRoom gratuitamente em offerroom.com",
        # Post-interview stats
        "stats_performance": "Seu desempenho",
        "stats_strength": "Seu ponto forte",
        "stats_weakness": "Trabalhe em",
        "stats_narrative": "Comunicação",
        "stats_technical": "Conhecimento técnico",
        "stats_logical": "Resolução de problemas",
        # Difficulty descriptions
        "difficulty_friendly_desc": "Entrevistador apoiador. Perguntas claras e bem estruturadas. Ambiente de baixa pressão.",
        "difficulty_realistic_desc": "Entrevistador profissional. Consciente do tempo com acompanhamentos profundos. Espera exemplos específicos e métricas.",
        "difficulty_brutal_desc": "Entrevistador exigente. Testará seu pensamento com casos extremos. Espera raciocínios profundos.",
        # Interview UX
        "interview_timer": "Tempo de entrevista",
        "interview_practice_again": "Praticar este cargo novamente",
        "interview_try_different": "Tentar cargo diferente",
        "interview_incomplete_warning": "Entrevista em andamento",
        "interview_resume": "Retomar entrevista",
        "interview_abandon": "Abandonar e voltar",
        "interview_incomplete_desc": "Você tem uma entrevista em andamento. Voltar irá abandoná-la.",
        "dev_badge": "🛠 MODO DEV",
    },
}


def t(key: str) -> str:
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(
        key, TRANSLATIONS["en"].get(key, key)
    )


# ── Firebase ────────────────────────────────────────────────────────────────────

@st.cache_resource
def _firebase_db():
    if not FIREBASE_AVAILABLE:
        return None
    try:
        if not firebase_admin._apps:
            cred_dict = {
                "type": "service_account",
                "project_id": _s("FIREBASE_PROJECT_ID"),
                "private_key": _s("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
                "client_email": _s("FIREBASE_CLIENT_EMAIL"),
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception:
        return None


# ── Password hashing ────────────────────────────────────────────────────────────

def _hash_pw(password: str) -> str:
    if BCRYPT_AVAILABLE:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def _verify_pw(password: str, hashed: str) -> bool:
    if BCRYPT_AVAILABLE:
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            return False
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest() == hashed


# ── Encryption ──────────────────────────────────────────────────────────────────

@st.cache_resource
def _fernet():
    if not CRYPTO_AVAILABLE:
        return None
    key = _s("ENCRYPTION_KEY")
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except Exception:
        return None


def _encrypt(text: str) -> str:
    if not text:
        return ""
    f = _fernet()
    if f:
        try:
            return f.encrypt(text.encode()).decode()
        except Exception:
            pass
    return text


def _decrypt(text: str) -> str:
    if not text:
        return ""
    f = _fernet()
    if f:
        try:
            return f.decrypt(text.encode()).decode()
        except Exception:
            pass
    return text


# ── User auth ───────────────────────────────────────────────────────────────────

def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def signup_user(email: str, password: str, confirm: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if not _valid_email(email):
        return False, t("auth_err_email")
    if len(password) < 8:
        return False, t("auth_err_password_short")
    if password != confirm:
        return False, t("auth_err_password_match")
    db = _firebase_db()
    if db is None:
        return False, t("auth_err_no_firebase")
    try:
        doc = db.collection("users").document(email).get()
        if doc.exists:
            return False, t("auth_err_email_taken")
        uid = str(uuid.uuid4())
        db.collection("users").document(email).set({
            "uid": uid,
            "email": email,
            "created_at": datetime.now(timezone.utc),
            "hashed_password": _hash_pw(password),
            "paid_interviews": 0,
        })
        st.session_state.current_user = {
            "uid": uid, "email": email, "paid_interviews": 0,
        }
        return True, ""
    except Exception as e:
        return False, t("auth_err_unknown")


def login_user(email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if not email or not password:
        return False, t("auth_err_invalid")
    db = _firebase_db()
    if db is None:
        return False, t("auth_err_no_firebase")
    try:
        doc = db.collection("users").document(email).get()
        if not doc.exists:
            return False, t("auth_err_invalid")
        data = doc.to_dict()
        if not _verify_pw(password, data.get("hashed_password", "")):
            return False, t("auth_err_invalid")
        # Read new field; fall back to old field name for existing accounts
        interviews = data.get("paid_interviews", data.get("paid_credits", 0))
        st.session_state.current_user = {
            "uid": data.get("uid", ""),
            "email": email,
            "paid_interviews": int(interviews),
        }
        return True, ""
    except Exception:
        return False, t("auth_err_unknown")


def _load_user_from_session_cookie():
    """Load user from a session token stored in query params or cookies."""
    # Check if user email is in query params (from payment redirect)
    email = st.query_params.get("user_email", "")
    if email and not st.session_state.get("current_user"):
        # User was redirected from payment, auto-login
        credits = get_credits(email)
        st.session_state.current_user = {
            "uid": "",
            "email": email,
            "paid_interviews": credits,
        }
        return True

    # Check session state - if user exists, keep them logged in
    if st.session_state.get("current_user"):
        return True

    return False


def logout_user():
    for k in [
        "current_user", "interview_active", "interview_messages", "interview_questions",
        "interview_q_num", "interview_stage", "interview_evaluation", "match_result",
        "cv_analysis", "cv_filename", "interview_start_time", "checkout_url", "saved_cvs",
        "current_session_id", "session_match_count", "session_interview_started",
        "use_custom_interviewer", "custom_interviewer_role", "custom_interviewer_context",
    ]:
        st.session_state.pop(k, None)
    st.session_state.auth_mode = False
    st.session_state.view = "setup"


# ── Credit operations ───────────────────────────────────────────────────────────

def get_credits(email: str) -> int:
    db = _firebase_db()
    if db is None or not email:
        return 0
    try:
        doc = db.collection("users").document(email).get()
        if not doc.exists:
            return 0
        d = doc.to_dict()
        return int(d.get("paid_interviews", d.get("paid_credits", 0)))
    except Exception:
        return 0


def add_credits(email: str, n: int):
    db = _firebase_db()
    if db is None or not email:
        return
    try:
        ref = db.collection("users").document(email)
        doc = ref.get()
        d = doc.to_dict() if doc.exists else {}
        current = int(d.get("paid_interviews", d.get("paid_credits", 0)))
        ref.set({"paid_interviews": current + n}, merge=True)
    except Exception:
        pass


def deduct_credit(email: str):
    db = _firebase_db()
    if db is None or not email:
        return
    try:
        ref = db.collection("users").document(email)
        doc = ref.get()
        d = doc.to_dict() if doc.exists else {}
        current = int(d.get("paid_interviews", d.get("paid_credits", 0)))
        ref.set({"paid_interviews": max(0, current - 1)}, merge=True)
    except Exception:
        pass




# ── Interview sessions ──────────────────────────────────────────────────────────

def create_interview_session(user_email: str, cv_filename: str, cv_text: str,
                             cv_analysis: dict) -> str:
    """Create a session when a new CV is uploaded. No token deducted."""
    db = _firebase_db()
    if db is None or not user_email:
        return ""
    try:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.collection("sessions").document(session_id).set({
            "session_id": session_id,
            "user_email": user_email,
            "cv_filename": cv_filename,
            "cv_text": cv_text,
            "cv_analysis": cv_analysis,
            "created_at": now,
            "expires_at": now + timedelta(days=7),
            "status": "active",
            "match_scores_used": 0,
            "interview_started": False,
            "token_reserved": False,
            "from_saved": False,
            "last_accessed": now,
        })
        return session_id
    except Exception:
        return ""


def create_interview_session_from_saved(user_email: str, cv_filename: str,
                                        cv_analysis: dict) -> str:
    """Create a session from a saved CV. No token deducted."""
    db = _firebase_db()
    if db is None or not user_email:
        return ""
    try:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.collection("sessions").document(session_id).set({
            "session_id": session_id,
            "user_email": user_email,
            "cv_filename": cv_filename,
            "cv_analysis": cv_analysis,
            "created_at": now,
            "expires_at": now + timedelta(days=7),
            "status": "active",
            "match_scores_used": 0,
            "interview_started": False,
            "token_reserved": False,
            "from_saved": True,
            "last_accessed": now,
        })
        return session_id
    except Exception:
        return ""


def update_session_match_count(session_id: str, count: int):
    """Increment match counter on the session document."""
    db = _firebase_db()
    if db is None or not session_id:
        return
    try:
        db.collection("sessions").document(session_id).update({
            "match_scores_used": count,
            "last_accessed": datetime.now(timezone.utc),
        })
    except Exception:
        pass


def mark_session_token_reserved(session_id: str):
    """Called when an interview starts — token has been deducted."""
    db = _firebase_db()
    if db is None or not session_id:
        return
    try:
        db.collection("sessions").document(session_id).update({
            "token_reserved": True,
            "interview_started": True,
        })
    except Exception:
        pass


def mark_session_completed(session_id: str, status: str = "completed"):
    """Mark a session as completed or abandoned."""
    db = _firebase_db()
    if db is None or not session_id:
        return
    try:
        db.collection("sessions").document(session_id).update({
            "status": status,
            "completed_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass


# ── CV storage ──────────────────────────────────────────────────────────────────

_MAX_CVS = 5


def save_cv_to_firebase(user_email: str, filename: str, cv_text: str,
                        cv_analysis=None) -> tuple[bool, str]:
    """Save a CV to Firebase.
    cv_text  — raw extracted text from the document.
    cv_analysis — dict returned by analyze_cv(); cached so reloads skip the Claude call.
    Returns (success, status) where status is 'saved'|'updated'|'limit'.
    """
    db = _firebase_db()
    if db is None or not user_email:
        return False, "no_db"
    try:
        docs = list(db.collection("cvs").where("email", "==", user_email).stream())
        # Same filename → update in place
        for d in docs:
            if d.to_dict().get("filename") == filename:
                d.reference.update({
                    "cv_text": cv_text,
                    "cv_analysis": cv_analysis,
                    "uploaded_at": datetime.now(timezone.utc),
                })
                return True, "updated"
        if len(docs) >= _MAX_CVS:
            return False, "limit"
        db.collection("cvs").add({
            "email": user_email,
            "filename": filename,
            "cv_text": cv_text,
            "cv_analysis": cv_analysis,
            "uploaded_at": datetime.now(timezone.utc),
            "is_primary": len(docs) == 0,
        })
        return True, "saved"
    except Exception as e:
        return False, str(e)


def get_user_cvs(user_email: str) -> list:
    """Return CVs for a user sorted by upload date (newest first)."""
    db = _firebase_db()
    if db is None or not user_email:
        return []
    try:
        docs = db.collection("cvs").where("email", "==", user_email).stream()
        items = [{"id": d.id, **d.to_dict()} for d in docs]
        items.sort(key=lambda x: x.get("uploaded_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        return items
    except Exception:
        return []


def delete_cv(cv_doc_id: str):
    """Delete a CV document by its Firestore ID."""
    db = _firebase_db()
    if db is None or not cv_doc_id:
        return
    try:
        db.collection("cvs").document(cv_doc_id).delete()
    except Exception:
        pass


def set_primary_cv(user_email: str, cv_doc_id: str):
    """Mark one CV as primary, clearing is_primary on all others."""
    db = _firebase_db()
    if db is None:
        return
    try:
        docs = list(db.collection("cvs").where("email", "==", user_email).stream())
        for d in docs:
            d.reference.update({"is_primary": d.id == cv_doc_id})
    except Exception:
        pass


# ── Interview data ──────────────────────────────────────────────────────────────

def _parse_eval_scores(text: str) -> dict:
    scores = {"final_score": 0.0, "narrative_score": 0, "technical_depth": 0, "logical_thinking": 0, "feedback": ""}
    for line in text.splitlines():
        if line.startswith("FINAL SCORE:"):
            try:
                scores["final_score"] = float(line.split(":")[1].strip().split("/")[0].strip())
            except Exception:
                pass
        elif "Narrative:" in line and "/5" in line:
            try:
                scores["narrative_score"] = int(line.split(":")[1].strip().split("/")[0].strip())
            except Exception:
                pass
        elif "Technical Depth:" in line and "/5" in line:
            try:
                scores["technical_depth"] = int(line.split(":")[1].strip().split("/")[0].strip())
            except Exception:
                pass
        elif "Logical Thinking:" in line and "/5" in line:
            try:
                scores["logical_thinking"] = int(line.split(":")[1].strip().split("/")[0].strip())
            except Exception:
                pass
    # Extract hire decision as feedback
    in_hire, hire_lines = False, []
    for line in text.splitlines():
        if line.strip().startswith("HIRE DECISION"):
            in_hire = True
            continue
        if in_hire and line.startswith("---"):
            break
        if in_hire and line.strip():
            hire_lines.append(line.strip())
    scores["feedback"] = " ".join(hire_lines[:2])
    return scores


def save_interview(user: dict, role_title: str, seniority: str, interviewer: str,
                   difficulty: str, eval_text: str, duration_minutes: float):
    db = _firebase_db()
    if db is None or not user:
        return
    scores = _parse_eval_scores(eval_text)
    try:
        db.collection("interviews").add({
            "uid": user.get("uid", ""),
            "email": user.get("email", ""),
            "date": datetime.now(timezone.utc),
            "role": f"{seniority} {role_title}",
            "interviewer": interviewer,
            "difficulty": difficulty,
            "final_score": scores["final_score"],
            "narrative_score": scores["narrative_score"],
            "technical_depth": scores["technical_depth"],
            "logical_thinking": scores["logical_thinking"],
            "feedback": scores["feedback"],
            "duration_minutes": round(duration_minutes, 1),
        })
    except Exception:
        pass


def get_user_interviews(email: str) -> list:
    db = _firebase_db()
    if db is None or not email:
        return []
    try:
        docs = db.collection("interviews").where("email", "==", email).stream()
        items = [{"id": d.id, **d.to_dict()} for d in docs]
        items.sort(key=lambda x: x.get("date", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        return items[:50]
    except Exception:
        return []


# ── Stripe ──────────────────────────────────────────────────────────────────────

CREDIT_PACKAGES = [
    ("single", "sidebar_buy_1",  1),
    ("5pack",  "sidebar_buy_5",  5),
    ("50pack", "sidebar_buy_50", 50),
]

_PKG_PRICE_KEYS = {
    "single": "STRIPE_PRICE_SINGLE",
    "5pack":  "STRIPE_PRICE_5PACK",
    "50pack": "STRIPE_PRICE_50PACK",
}

def _get_price_id_for_package(package_id: str) -> str:
    currency = "BRL"
    base_key = _PKG_PRICE_KEYS[package_id]
    return _s(f"{base_key}_{currency}")


def create_checkout_session(price_id: str, email: str, credits: int) -> str:
    _stripe_lib.api_key = _s("STRIPE_SECRET_KEY")
    app_url = _s("APP_URL")
    if not app_url:
        app_url = "https://offer-room.streamlit.app"
    session = _stripe_lib.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="payment",
        customer_email=email or None,
        success_url=(
            f"{app_url}/?payment_success=1"
            f"&session_id={{CHECKOUT_SESSION_ID}}"
            f"&user_email={email}&credits={credits}"
        ),
        cancel_url=f"{app_url}/?payment_cancelled=1",
    )
    return session.url


def _is_session_processed(session_id: str) -> bool:
    db = _firebase_db()
    if db is None:
        return False
    try:
        return db.collection("processed_sessions").document(session_id).get().exists
    except Exception:
        return False


def _mark_session_processed(session_id: str):
    db = _firebase_db()
    if db is None:
        return
    try:
        db.collection("processed_sessions").document(session_id).set({"ok": True})
    except Exception:
        pass


def handle_payment_success():
    params = st.query_params
    if params.get("payment_success") == "1":
        session_id = params.get("session_id", "")
        user_email = params.get("user_email", "")
        credits_str = params.get("credits", "1")
        msg = ""
        if session_id and user_email and STRIPE_AVAILABLE:
            try:
                _stripe_lib.api_key = _s("STRIPE_SECRET_KEY")
                session = _stripe_lib.checkout.Session.retrieve(session_id)
                if session.payment_status == "paid" and not _is_session_processed(session_id):
                    n = int(credits_str)
                    add_credits(user_email, n)
                    _mark_session_processed(session_id)
                    msg = t("payment_success").format(n=n)
                    user = st.session_state.get("current_user")
                    if user and user.get("email") == user_email:
                        st.session_state.current_user["paid_interviews"] = get_credits(user_email)
            except Exception as e:
                msg = t("payment_error").format(e=e)
        if msg:
            st.session_state.payment_message = msg
        st.query_params.clear()
        st.rerun()
    elif params.get("payment_cancelled") == "1":
        st.session_state.payment_message = t("payment_cancelled")
        st.query_params.clear()
        st.rerun()


# ── API key & client ────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    return key or ""


def _client() -> anthropic.Anthropic:
    key = _get_api_key()
    if not key:
        st.stop()
    return anthropic.Anthropic(api_key=key)


# ── Voice recorder component ────────────────────────────────────────────────────

_VOICE_COMPONENT_HTML = """\
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
       padding:10px 12px;background:transparent}
  .row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  button{cursor:pointer;border:1.5px solid #e5e7eb;border-radius:6px;
         padding:5px 14px;font-size:.82rem;font-weight:500;background:#fff;
         white-space:nowrap;transition:background .12s,border-color .12s}
  button:hover:not(:disabled){background:#f3f4f6}
  #recBtn{background:#2563eb;color:#fff;border-color:#2563eb}
  #recBtn:hover{background:#1d4ed8 !important;border-color:#1d4ed8}
  #recBtn.rec{background:#dc2626;border-color:#dc2626}
  #recBtn.rec:hover{background:#b91c1c !important;border-color:#b91c1c}
  #submitBtn{background:#16a34a;color:#fff;border-color:#16a34a;display:none}
  #submitBtn:hover{background:#15803d !important}
  #clearBtn{display:none}
  #status{font-size:.78rem;color:#6b7280;margin-top:6px;min-height:16px}
  #interimBox{font-size:.83rem;color:#9ca3af;font-style:italic;background:#f9fafb;
              border-radius:4px;padding:5px 8px;margin-top:5px;
              min-height:22px;display:none}
  #transcriptBox{font-size:.88rem;color:#111827;line-height:1.5;background:#eff6ff;
                 border:1px solid #bfdbfe;border-radius:6px;padding:8px 10px;
                 margin-top:6px;min-height:36px;display:none;white-space:pre-wrap}
  #errMsg{font-size:.82rem;color:#dc2626;margin-top:6px;display:none}
  #noSupport{font-size:.82rem;color:#f97316;margin-top:4px;display:none}
</style></head><body>
<div class="row">
  <button id="recBtn"    onclick="toggleRec()">🎤 Start</button>
  <button id="clearBtn"  onclick="clearAll()">Clear</button>
  <button id="submitBtn" onclick="doSubmit()">✓ Submit answer</button>
</div>
<div id="status"></div>
<div id="interimBox"></div>
<div id="transcriptBox"></div>
<div id="errMsg"></div>
<div id="noSupport">⚠️ Voice input requires Chrome, Edge, or Safari.</div>
<script>
var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) {
  document.getElementById('noSupport').style.display = 'block';
  document.getElementById('recBtn').style.display = 'none';
}
var rec = null, finalT = '', isRec = false, langCode = 'en-US';

// ── Streamlit component protocol ──────────────────────────────────────────────
window.parent.postMessage({type:'streamlit:componentReady', apiVersion:1}, '*');
window.addEventListener('message', function(e) {
  if (e.data && e.data.type === 'streamlit:render') {
    langCode = (e.data.args && e.data.args.lang) ? e.data.args.lang : 'en-US';
    if (rec) rec.lang = langCode;
  }
});
function send(v) {
  window.parent.postMessage({type:'streamlit:setComponentValue', value:v}, '*');
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(s) { document.getElementById('status').textContent = s; }
function setError(s) {
  var el = document.getElementById('errMsg');
  el.textContent = s; el.style.display = s ? 'block' : 'none';
}
function showTranscript(t) {
  var el = document.getElementById('transcriptBox');
  el.textContent = t; el.style.display = t ? 'block' : 'none';
}

// ── Recording ─────────────────────────────────────────────────────────────────
function toggleRec() { isRec ? stopRec(true) : startRec(); }

function startRec() {
  if (!SR) return;
  setError('');
  rec = new SR();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = langCode;

  rec.onstart = function() {
    isRec = true;
    document.getElementById('recBtn').textContent = '⏹ Stop';
    document.getElementById('recBtn').classList.add('rec');
    document.getElementById('interimBox').style.display = 'block';
    setStatus('🔴 Listening\u2026');
  };

  rec.onresult = function(e) {
    var interim = '';
    for (var i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) finalT += e.results[i][0].transcript + ' ';
      else interim += e.results[i][0].transcript;
    }
    document.getElementById('interimBox').textContent = interim || '\u2026';
    if (finalT.trim()) {
      showTranscript((finalT + interim).trim());
      document.getElementById('clearBtn').style.display = 'inline-block';
      document.getElementById('submitBtn').style.display = 'inline-block';
    }
  };

  rec.onerror = function(e) {
    var msgs = {
      'not-allowed': '\u26a0\ufe0f Microphone access denied \u2014 check browser permissions.',
      'no-speech':   'No speech detected. Click Start to try again.',
      'network':     '\u26a0\ufe0f Network error during transcription.',
      'aborted':     ''
    };
    setError(msgs[e.error] !== undefined ? msgs[e.error] : 'Error: ' + e.error);
    stopRec(false);
  };

  rec.onend = function() { if (isRec) rec.start(); };
  try { rec.start(); }
  catch(e) { setError('\u26a0\ufe0f Could not access microphone: ' + e.message); }
}

function stopRec(updateStatus) {
  isRec = false;
  if (rec) { rec.onend = null; rec.stop(); rec = null; }
  document.getElementById('recBtn').textContent = '🎤 Record more';
  document.getElementById('recBtn').classList.remove('rec');
  document.getElementById('interimBox').style.display = 'none';
  if (updateStatus && finalT.trim()) {
    setStatus('Done. Edit above if needed, then submit.');
  }
}

function clearAll() {
  finalT = '';
  stopRec(false);
  setStatus(''); setError('');
  showTranscript('');
  document.getElementById('interimBox').style.display = 'none';
  document.getElementById('clearBtn').style.display = 'none';
  document.getElementById('submitBtn').style.display = 'none';
  document.getElementById('recBtn').textContent = '🎤 Start';
  document.getElementById('recBtn').classList.remove('rec');
  send(null);
}

function doSubmit() {
  var text = finalT.trim();
  if (!text) return;
  stopRec(false);
  setStatus('\u2713 Answer submitted!');
  send(text);
  setTimeout(function() { clearAll(); setStatus(''); }, 1200);
}
</script></body></html>
"""


@st.cache_resource
def _get_voice_component():
    """Write voice recorder HTML to a temp dir and declare a Streamlit component.
    Returns the component callable, or None if the setup fails."""
    try:
        import streamlit.components.v1 as components
        tmp_dir = tempfile.mkdtemp(prefix="offerroom_voice_")
        with open(os.path.join(tmp_dir, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(_VOICE_COMPONENT_HTML)
        return components.declare_component("voice_recorder", path=tmp_dir)
    except Exception as e:
        print(f"Voice component load error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ── Page header helpers ─────────────────────────────────────────────────────────

_LANG_OPTIONS = {"en": "🇺🇸 English", "es": "🇪🇸 Español", "pt": "🇧🇷 Português"}


def _lang_selector(key_suffix: str = ""):
    """Language dropdown selector."""
    current = st.session_state.get("language", "en")
    options = list(_LANG_OPTIONS.keys())
    idx = options.index(current) if current in options else 0
    selected = st.selectbox(
        "language",
        options=options,
        format_func=lambda c: _LANG_OPTIONS[c],
        index=idx,
        label_visibility="collapsed",
        key=f"lang_sel{key_suffix}",
    )
    if selected != current:
        st.session_state.language = selected
        st.rerun()


def _app_header(back_label: str = "", back_key: str = "", back_action=None):
    """
    Top bar: [back?] [flags] … [account info]
    back_action is a callable executed when back button is clicked.
    """
    user = st.session_state.get("current_user")

    # Column layout: back? | flags×3 | spacer | account
    has_back = bool(back_label and back_action)
    col_widths = ([2] if has_back else []) + [2, 7, 3]
    cols = st.columns(col_widths)
    offset = 0

    if has_back:
        if cols[0].button(back_label, key=back_key):
            back_action()
            st.rerun()
        offset = 1

    # Language selector
    with cols[offset]:
        _lang_selector(key_suffix=f"_hdr_{back_key}")

    # Account info (right side, last col)
    acct_col = cols[-1]
    if _DEV_MODE:
        acct_col.markdown(
            f'<span style="background:#fbbf24;color:#000;border-radius:6px;'
            f'padding:2px 8px;font-size:0.75rem;font-weight:700;">{t("dev_badge")}</span>',
            unsafe_allow_html=True,
        )
    elif user:
        n_left = user.get("paid_interviews", 0)
        _cr = "#ef4444" if n_left == 0 else "#f97316" if n_left <= 2 else "#6b7280"
        cr_html = (
            f'<span style="color:{_cr};font-weight:600;">'
            f'{t("acct_credits").format(n=n_left)}</span>'
        )
        acct_col.markdown(
            f'<p style="text-align:right;font-size:0.75rem;margin:0;line-height:1.5;">'
            f'<span style="color:#6b7280;">{user["email"]}</span><br>{cr_html}</p>',
            unsafe_allow_html=True,
        )
    st.divider()


# ── CV extraction ───────────────────────────────────────────────────────────────

def extract_cv_text(uploaded_file) -> str:
    data = uploaded_file.read()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        try:
            import fitz
            doc = fitz.open(stream=data, filetype="pdf")
            return "\n".join(p.get_text() for p in doc)
        except ImportError:
            st.error("pymupdf not installed")
            return ""
    if name.endswith((".doc", ".docx")):
        try:
            from docx import Document
            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        except ImportError:
            st.error("python-docx not installed")
            return ""
    return ""


# ── Claude helpers ──────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

    # Handle case where Claude adds text before/after JSON
    if not raw.startswith("{"):
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end+1]

    return json.loads(raw)


def _safe(text: str) -> str:
    return text.replace("$", "\\$")


def _stream_safe(gen) -> str:
    placeholder = st.empty()
    raw = ""
    for chunk in gen:
        raw += chunk
        placeholder.markdown(_safe(raw) + " ▌")
    placeholder.markdown(_safe(raw))
    return raw


# ── Claude API functions ────────────────────────────────────────────────────────

def analyze_cv(cv_text: str) -> dict:
    if _DEV_MODE:
        return {
            "last_5_experiences": [
                {"title": "Senior Product Manager", "company": "Acme Corp",
                 "period": "Jan 2022 – Present (2+ yrs)",
                 "summary": "Led cross-functional team of 8 to ship 3 major features. Grew DAU 40%."},
                {"title": "Product Manager", "company": "Beta Inc",
                 "period": "Mar 2019 – Dec 2021 (2 yrs 9 mo)",
                 "summary": "Owned B2B SaaS roadmap. Reduced churn 15% via retention features."},
            ],
            "top_5_skills": ["Product strategy", "Stakeholder management", "Data analysis",
                             "Roadmap planning", "Go-to-market"],
            "top_3_weak_areas": ["Technical depth", "International markets", "Hardware/IoT"],
            "suggested_seniority": "Senior",
        }
    prompt = f"""Analyze this CV and return ONLY a JSON object — no markdown, no fences, no extra text.

{{
  "last_5_experiences": [
    {{
      "title": "job title",
      "company": "company name",
      "period": "e.g. Jan 2020 – Mar 2022 (2 yrs 2 mo)",
      "summary": "2-sentence summary of role and key achievements"
    }}
  ],
  "top_5_skills": ["skill1", "skill2", "skill3", "skill4", "skill5"],
  "top_3_weak_areas": ["area1", "area2", "area3"],
  "suggested_seniority": "one of: Associate, Junior, Mid, Senior, Principal, Director, Head, VP, C-Level"
}}

Rules:
- Experiences from most recent to oldest, max 5
- weak_areas = skills/domains absent or barely demonstrated

CV:
{cv_text[:8000]}"""
    r = _client().messages.create(
        model="claude-sonnet-4-6", max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(r.content[0].text)


def fetch_and_summarize(url: str) -> str:
    if _DEV_MODE:
        return ("[DEV] Acme Corp is a fast-growing B2B SaaS company in the productivity space, "
                "serving 5,000+ enterprise customers globally. Series B, ~200 employees.")
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        st.error("Missing packages — run: pip install requests beautifulsoup4")
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OfferRoom/1.0)"}
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = (soup.find("meta", {"name": "description"})
                or soup.find("meta", {"property": "og:description"}))
        meta_text = meta.get("content", "") if meta else ""
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        body = soup.get_text(separator=" ", strip=True)[:4000]
        raw = f"{meta_text}\n\n{body}"
    except Exception as exc:
        st.error(f"Could not fetch {url}: {exc}")
        return ""
    r = _client().messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=200,
        messages=[{"role": "user", "content": (
            "Based on this website content, write a concise 2–3 sentence company description "
            "covering what they do, their industry, and their stage/size if evident.\n\n"
            f"{raw}\n\nReturn only the description, no labels or preamble."
        )}],
    )
    return r.content[0].text.strip()


def score_match(cv: dict, role: str, seniority: str, company: str, jd: str) -> dict:
    if _DEV_MODE:
        return {
            "score": 4,
            "explanation": ("[DEV] Strong match. 4+ years as Product Manager aligns well with "
                            "the Senior PM role. B2B SaaS and cross-functional leadership directly relevant."),
        }
    prompt = f"""You are a senior recruiter scoring a CV against a job. Score 1–5:

1 – No match: different industry, role type, and experience level
2 – Distant match: some overlap but experience very far off
3 – Average match: career change with transferable skills
4 – Good match: similar role, adjacent industry, seniority within 1 level
5 – Perfect match: same role, same ecosystem, right seniority

CV PROFILE:
{json.dumps(cv, indent=2)}

JOB:
- Role: {role}
- Seniority: {seniority}
- Company: {company or "Not specified"}
- Job Description: {jd or "Not provided"}

Return ONLY JSON, no fences:
{{"score": <integer 1-5>, "explanation": "<2-3 sentences citing specific CV evidence>"}}"""
    r = _client().messages.create(
        model="claude-sonnet-4-6", max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(r.content[0].text)


# ── Interview personas & difficulty ────────────────────────────────────────────

PERSONAS: dict[str, dict] = {
    "First-Round Recruiter": {
        "subtitle": "CV Check & Culture Fit",
        "mindset": (
            "You are screening for baseline qualification. You assess clarity of communication, "
            "check alignment with the job description, and look for red flags. "
            "You care about career narrative and motivation."
        ),
        "focus": (
            "Walk me through your background. Why this role? Why this company? "
            "Basic competency validation. Culture alignment. Motivation and career narrative."
        ),
        "behavior": (
            "Polite but structured. Time-conscious. Surface-level but attentive. "
            "You will flag inconsistencies in the CV or story."
        ),
    },
    "Hiring Manager": {
        "subtitle": "Future Direct Boss",
        "mindset": (
            "You need to know: can this person solve my real problems? "
            "Will I trust them with ownership? Can they operate autonomously?"
        ),
        "focus": (
            "Past ownership. Decision-making process. Results delivered. "
            "Trade-offs made. Problem-solving depth. Stakeholder management."
        ),
        "behavior": (
            "Direct. Practical. You push for specifics and ask 'why' repeatedly. "
            "You test real-world judgment. You have little patience for vague answers."
        ),
    },
    "Software Engineer": {
        "subtitle": "Technical Peer",
        "mindset": (
            "Do they actually understand what they claim? "
            "Can they collaborate effectively? Are they technically rigorous?"
        ),
        "focus": (
            "System thinking. Technical trade-offs. Architecture decisions. "
            "Edge cases. Failure modes. Debugging logic."
        ),
        "behavior": (
            "Detail-oriented. You challenge shallow understanding. "
            "You request concrete examples and will follow up on inconsistencies."
        ),
    },
    "Product Specialist": {
        "subtitle": "PM / Designer Peer",
        "mindset": (
            "Do they think in outcomes? Do they understand users? "
            "Do they balance business goals and UX?"
        ),
        "focus": (
            "User insight. Metrics. Prioritization logic. Roadmapping. "
            "Experimentation. Cross-functional alignment."
        ),
        "behavior": (
            "Analytical. You ask about trade-offs and probe decision frameworks. "
            "You test for structured thinking."
        ),
    },
    "CMO": {
        "subtitle": "Chief Marketing Officer",
        "mindset": (
            "How does this person impact growth? "
            "Do they understand positioning and revenue? Are they commercially aware?"
        ),
        "focus": (
            "Market understanding. Competitive landscape. Growth metrics. "
            "Customer acquisition. Brand implications. Revenue impact."
        ),
        "behavior": (
            "Strategic. Business-oriented. ROI-focused. "
            "You challenge weak commercial logic and expect quantified thinking."
        ),
    },
    "CFO": {
        "subtitle": "Chief Financial Officer",
        "mindset": (
            "Does this person understand cost, efficiency, and financial trade-offs? "
            "Are they capital disciplined?"
        ),
        "focus": (
            "ROI. Unit economics. Budget trade-offs. Resource allocation. "
            "Risk assessment. Measurable financial impact."
        ),
        "behavior": (
            "Skeptical. Numbers-driven. You cut through fluff and always ask for quantification."
        ),
    },
    "CTO": {
        "subtitle": "Chief Technology Officer",
        "mindset": (
            "Can this person operate in complexity? "
            "Do they understand scale, architecture, and long-term implications?"
        ),
        "focus": (
            "Technical depth. Scalability. Risk mitigation. Engineering alignment. "
            "Technical debt awareness. System-level thinking."
        ),
        "behavior": (
            "Strategic but technical. You push for architectural clarity, "
            "test long-term thinking, and look for systems awareness."
        ),
    },
    "CEO": {
        "subtitle": "Chief Executive Officer",
        "mindset": (
            "Will this person raise the overall bar? "
            "Do they think like an owner? Do they understand company-level impact?"
        ),
        "focus": (
            "Strategic thinking. Leadership. Risk tolerance. "
            "Long-term impact. Decision quality. Accountability."
        ),
        "behavior": (
            "High-level. Vision-oriented. You challenge superficial thinking "
            "and push for clarity and conviction."
        ),
    },
    "Custom Interviewer": {
        "subtitle": "Define your own interview",
        "mindset": (
            "You are a custom interviewer defined by the candidate's input. "
            "Adapt your behavior and questions based on the specific role and context provided."
        ),
        "focus": (
            "Determined by the candidate's role and background. "
            "Ask questions relevant to their specific position and industry."
        ),
        "behavior": (
            "Professional, focused on the candidate's actual role. "
            "Questions tailored to their specific industry and experience level."
        ),
    },
}

# (emoji, first-name) per interviewer persona — used for humanised chat display
PERSONA_META: dict[str, tuple] = {
    "First-Round Recruiter": ("👨", "Mark"),
    "Hiring Manager":        ("👩", "Anna"),
    "Software Engineer":     ("👩", "Alyssa"),
    "Product Specialist":    ("👨", "Nadeem"),
    "CMO":                   ("👨", "Wilt"),
    "CFO":                   ("👩", "Mary"),
    "CTO":                   ("👨", "Andrew"),
    "CEO":                   ("👩", "Jen"),
    "Custom Interviewer":    ("👨", "Pete"),
}


def _strip_iv_prefix(text: str) -> str:
    """Strip [ROLE – Name] prefixes that dev mode or the AI may prepend."""
    return re.sub(r'^\[[^\]]+\]\s*', '', text)


DIFFICULTY_MODULATION: dict[str, dict] = {
    "Friendly": {
        "tone": "Supportive, calm, encouraging, professional but warm.",
        "intent": (
            "Help the candidate articulate their thoughts. Validate baseline competence. "
            "Allow space for clarification. Reduce stress to observe natural thinking."
        ),
        "question_style": "Open-ended, clear, structured. Not intentionally tricky. Minimal ambiguity.",
        "followups": (
            "Ask for clarification if unclear. Offer light nudges ('Can you expand on that?'). "
            "Allow rephrasing. Do not aggressively interrupt."
        ),
        "tolerance": "Moderate tolerance for vague language, missing numbers, and imperfect structure.",
        "pressure": "Low. No interruption mid-answer. No hostile framing.",
        "evaluation": "Assumes good intent. Focuses on potential. Forgiving of communication flaws.",
        "escalation": (
            "Avoid adversarial questioning. Focus on narrative clarity and baseline reasoning."
        ),
    },
    "Realistic": {
        "tone": "Neutral, professional, slightly skeptical, time-conscious.",
        "intent": (
            "Simulate real-world interview rigor. Test structured thinking, ownership, clarity, "
            "and measurable impact."
        ),
        "question_style": (
            "Clear but probing. Requires examples, numbers where applicable, explicit trade-offs. "
            "Mix of behavioral and situational questions."
        ),
        "followups": (
            "Interrupt if the answer is drifting. Ask 'Why?' multiple times. Ask for metrics. "
            "Ask for concrete examples. Challenge inconsistencies."
        ),
        "tolerance": (
            "Low tolerance for fluff, buzzwords, or abstract claims. "
            "Requires quantification when reasonable."
        ),
        "pressure": (
            "Moderate. Will redirect. Will cut off overly long answers. "
            "Will ask pointed clarification questions."
        ),
        "evaluation": "Objective. Focuses on demonstrated competence. Compares against real hiring bar.",
        "escalation": (
            "Push for clarity but do not intentionally destabilize. "
            "Ask for at least one measurable outcome per experience."
        ),
    },
    "Brutal": {
        "tone": "Direct, sharp, high-expectation, skeptical. Occasionally confrontational but never disrespectful.",
        "intent": (
            "Stress-test thinking. Expose weak reasoning. Reveal superficial understanding. "
            "Test composure under pressure. Simulate elite hiring bar."
        ),
        "question_style": (
            "Ambiguous framing. Edge-case heavy. Scenario-based. "
            "Asks for decisions under constraints. No perfect answers."
        ),
        "followups": (
            "Interrupt vague answers immediately. Demand specific numbers and frameworks. "
            "Challenge contradictions. Ask counterfactuals. Ask 'What would break?', "
            "'What did you miss?', 'What was the cost?'. Push into the weakest area detected."
        ),
        "tolerance": (
            "Zero tolerance for buzzwords, hand-waving, generic leadership claims, "
            "or missing metrics when impact is mentioned."
        ),
        "pressure": (
            "High. May change direction abruptly. May invalidate weak reasoning. "
            "Will test edge cases and failure scenarios."
        ),
        "evaluation": (
            "Compares to top 10–20% bar. Assumes candidate must justify their presence. "
            "Hires only if strong signal is consistent throughout."
        ),
        "escalation": (
            "Increase follow-up depth by 2 levels. Always push one level deeper than the initial answer. "
            "Introduce at least one edge-case scenario per question. "
            "Challenge at least one assumption per major answer. "
            "Request quantification whenever impact is mentioned. Do not soften critique."
        ),
    },
}


def _difficulty_block(difficulty: str) -> str:
    d = DIFFICULTY_MODULATION.get(difficulty, {})
    if not d:
        return f"Difficulty: {difficulty}"
    return (
        f"DIFFICULTY: {difficulty}\n"
        f"TONE: {d['tone']}\n"
        f"INTENT: {d['intent']}\n"
        f"QUESTION STYLE: {d['question_style']}\n"
        f"FOLLOW-UP BEHAVIOR: {d['followups']}\n"
        f"TOLERANCE: {d['tolerance']}\n"
        f"PRESSURE LEVEL: {d['pressure']}\n"
        f"EVALUATION STANDARD: {d['evaluation']}\n"
        f"ESCALATION RULE: {d['escalation']}"
    )


def _persona_block(interviewer: str) -> str:
    p = PERSONAS.get(interviewer, {})
    if not p:
        return f"Interviewer: {interviewer}"
    return (
        f"PERSONA: {interviewer} — {p['subtitle']}\n"
        f"MINDSET: {p['mindset']}\n"
        f"FOCUS AREAS: {p['focus']}\n"
        f"BEHAVIOR: {p['behavior']}"
    )


def _context_block(interviewer, role_title, seniority, company_summary, job_description) -> str:
    company_info = company_summary.strip() if company_summary else "Not specified"
    jd_info = job_description.strip() if job_description else "Not provided"
    return (
        "CONTEXT INTEGRATION REQUIREMENT\n"
        "Every question must incorporate, whenever possible:\n"
        f"- Role: {seniority} {role_title}\n"
        f"- Company context: {company_info}\n"
        f"- Job description: {jd_info}\n"
        "- The company's industry, business model, customer type (B2B/B2C/enterprise/consumer)\n"
        "- Constraints implied by the industry (regulatory, technical, safety, compliance, scale)\n\n"
        "The interviewer must tailor scenarios to this company context, reference realistic "
        "business constraints, adapt trade-offs to the company's environment, and avoid "
        "generic context-free questions.\n\n"
        "ANTI-GENERIC RULE: Ground every question in this company's industry, constraints, "
        "and customer type — never ask generic textbook questions.\n\n"
        "CONSISTENCY RULE: Maintain contextual anchoring throughout the entire interview.\n\n"
        f"PERSONA LENS — {interviewer} interprets company context through its own lens:\n"
        "- Recruiter: culture fit within this specific industry.\n"
        "- Hiring Manager: real problems specific to this company.\n"
        "- Engineer: technical systems likely in this industry.\n"
        "- Product Specialist: user questions tailored to this company's user base.\n"
        "- CMO: market dynamics specific to this industry.\n"
        "- CFO: financial trade-offs specific to this business model.\n"
        "- CTO: technical constraints relevant to this environment.\n"
        "- CEO: long-term strategic implications within this industry.\n\n"
        "DEPTH RULE: If detailed company info is provided, use it heavily. "
        "If limited, infer from the industry — stay grounded."
    )


# ── Interview Claude functions ─────────────────────────────────────────────────

def generate_interview_setup(cv_analysis, role_title, seniority, company_summary,
                              job_description, interviewer, difficulty, language="en",
                              custom_role: str = "", custom_context: str = "") -> dict:
    if _DEV_MODE:
        return {
            "persona_intro": (
                f"[DEV – {interviewer}] Great to meet you. I've reviewed your background — "
                "let's dive right in. I want to understand how you think under pressure."
            ),
            "questions": [
                "Tell me about a product you're most proud of building. What was your specific contribution?",
                "Walk me through a time you had to kill a feature or project. How did you handle stakeholders?",
                "How do you decide what to build next when you have 10 good ideas and bandwidth for only 2?",
                "Describe a situation where engineering pushed back hard on your roadmap. What happened?",
                "What would you do in your first 90 days in this role?",
            ],
        }
    lang_rule = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("lang_instruction", "")

    if custom_role:
        # Custom mode: override persona context with user-defined role/context
        effective_role = custom_role
        effective_company = custom_context or f"Interviewing for: {custom_role}"
        effective_jd = ""
    else:
        effective_role = f"{seniority} {role_title}"
        effective_company = company_summary or ""
        effective_jd = job_description or ""

    system = (
        "You are an AI Interview Simulator. Fully embody the selected persona.\n\n"
        "Rules:\n"
        "- Stay in character throughout.\n"
        "- Ask questions this persona would realistically ask.\n"
        "- Adapt questions to the candidate's CV and target role.\n"
        "- Do not provide coaching or feedback — only ask questions.\n\n"
        + _context_block(interviewer, effective_role, seniority, effective_company, effective_jd)
        + f"\n\n{lang_rule}"
    )
    target_role_line = custom_role if custom_role else f"{seniority} {role_title}"
    context_line = effective_company or "Not specified"
    jd_line = effective_jd or "Not provided"
    prompt = f"""{_persona_block(interviewer)}

{_difficulty_block(difficulty)}

TARGET ROLE: {target_role_line}
COMPANY CONTEXT: {context_line}
JOB DESCRIPTION: {jd_line}
CANDIDATE CV SUMMARY:
{json.dumps(cv_analysis, indent=2)}

Generate:
1. A brief, in-character opening (2–3 sentences, first person). Reflect tone and pressure. Do not ask a question yet.
2. Exactly 5 interview questions: grounded in persona mindset, calibrated to difficulty, deeply tailored to company context, diverse across dimensions, ordered warm-up to deep.

CRITICAL: Return ONLY a valid JSON object with NO other text, NO markdown, NO explanation. The entire response must be valid JSON only.
{{"persona_intro": "...", "questions": ["Q1", "Q2", "Q3", "Q4", "Q5"]}}"""
    r = _client().messages.create(
        model="claude-opus-4-5-20251101", max_tokens=1500,
        system=system, messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(r.content[0].text)


def _stream_followup(base_question, user_answer, interviewer, difficulty,
                     role_title, seniority, company_summary="", job_description="", language="en"):
    if _DEV_MODE:
        yield "[DEV] Interesting — can you give me a specific metric or number to back that up?"
        return
    lang_rule = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("lang_instruction", "")
    system = (
        "You are an AI Interview Simulator fully embodying an interviewer persona. "
        "You do not provide coaching or feedback. You only ask questions.\n\n"
        f"{_persona_block(interviewer)}\n\n"
        f"{_difficulty_block(difficulty)}\n\n"
        "CONSISTENCY RULE: Do not change tone mid-session. Never be sycophantic.\n\n"
        + _context_block(interviewer, role_title, seniority, company_summary, job_description)
        + f"\n\n{lang_rule}"
    )
    prompt = (
        f"You are interviewing a candidate for a {seniority} {role_title} position.\n\n"
        f"You asked: \"{base_question}\"\n\n"
        f"The candidate answered: \"{user_answer}\"\n\n"
        f"Generate ONE follow-up question that targets the weakest point in their answer, "
        f"applies the defined pressure level, reflects this persona's mindset, and is anchored "
        f"to the company context. Single direct question — no preamble, no label.\n\n"
        f"Return ONLY the follow-up question."
    )
    with _client().messages.stream(
        model="claude-sonnet-4-6", max_tokens=300,
        system=system, messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


def _stream_closing(interviewer, role_title, seniority, language="en"):
    if _DEV_MODE:
        yield "[DEV] Thank you for your time today. We'll be in touch within the week regarding next steps."
        return
    p = PERSONAS.get(interviewer, {})
    lang_rule = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("lang_instruction", "")
    system = (
        f"You are a {interviewer} wrapping up a job interview for a {seniority} {role_title} position. "
        f"{p.get('behavior', '')} Stay in character. Do not give feedback. {lang_rule}"
    )
    prompt = (
        f"The interview has concluded. Deliver a brief in-character closing (2–3 sentences). "
        f"Thank the candidate, mention next steps will follow, stay true to persona and tone. "
        f"Return only the closing statement."
    )
    with _client().messages.stream(
        model="claude-haiku-4-5-20251001", max_tokens=150,
        system=system, messages=[{"role": "user", "content": prompt}],
    ) as stream:
        yield from stream.text_stream


def generate_evaluation(messages, role_title, seniority, interviewer, difficulty, language="en") -> str:
    if _DEV_MODE:
        return (
            "FINAL SCORE: 4.0 / 5\n\n"
            "Category Breakdown:\n"
            "- Narrative: 4/5\n"
            "- Technical Depth: 4/5\n"
            "- Logical Thinking: 4/5\n\n"
            "---\n\n"
            "WHAT WENT WELL\n"
            "- Structured answers with clear examples\n"
            "- Demonstrated strategic thinking throughout\n"
            "- Good communication and concise delivery\n\n"
            "WHAT NEEDS IMPROVEMENT\n"
            "- Could add more quantitative evidence\n"
            "- Technical depth on implementation details could be stronger\n\n"
            "---\n\n"
            "HIRE DECISION\n"
            "Hire\n"
            "Strong candidate with relevant experience and clear communication skills. "
            "Would benefit from deeper technical grounding but shows solid product instincts. "
            "[DEV MODE — static evaluation]\n\n"
            "---\n\n"
            "ANSWER IMPROVEMENT SECTION\n"
            "N/A — DEV MODE, no real answers to evaluate."
        )
    eval_lang = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("eval_lang_instruction", "")
    system = (
        "You are switching from Interviewer Mode to Evaluation Mode.\n\n"
        "Analyze the full interview transcript. Evaluate objectively based on demonstrated answers only.\n\n"
        "SCORING FRAMEWORK — 3 categories (1–5 each):\n\n"
        "1) Narrative: Clarity, structure, coherence, storytelling, confidence.\n"
        "   1=Disorganized  2=Weak  3=Clear but inconsistent  4=Strong  5=Exceptional\n\n"
        "2) Technical Depth: Domain knowledge, trade-offs, metrics, edge cases.\n"
        "   1=Superficial  2=Limited  3=Solid  4=Strong  5=Exceptional mastery\n\n"
        "3) Logical Thinking: Structured reasoning, cause-effect, frameworks, prioritization.\n"
        "   1=Illogical  2=Weak  3=Generally logical  4=Strong  5=Elite\n\n"
        "FINAL SCORE = average of three categories, to 1 decimal.\n\n"
        "OUTPUT FORMAT (exact):\n\n"
        "FINAL SCORE: X.X / 5\n\n"
        "Category Breakdown:\n"
        "- Narrative: X/5\n"
        "- Technical Depth: X/5\n"
        "- Logical Thinking: X/5\n\n"
        "---\n\n"
        "WHAT WENT WELL (max 5 bullets)\n"
        "- ...\n\n"
        "WHAT NEEDS IMPROVEMENT (max 5 bullets)\n"
        "- ...\n\n"
        "---\n\n"
        "HIRE DECISION\n"
        "Choose one: Strong Hire / Hire / Lean Hire / Lean No / No Hire\n"
        "Follow with 3–5 sentences explaining the decision.\n\n"
        "---\n\n"
        "ANSWER IMPROVEMENT SECTION\n"
        "Up to 3 weakest answers: quote excerpt → explain why weak → stronger example → why better.\n\n"
        "Be specific, constructive, rigorous. Do not inflate scores.\n\n"
        + eval_lang
    )
    transcript = "\n\n".join(
        f"[{'INTERVIEWER' if m['role'] == 'assistant' else 'CANDIDATE'}]: {m['content']}"
        for m in messages
    )
    prompt = (
        f"Interview context: {interviewer} interviewing a candidate for {seniority} {role_title}. "
        f"Difficulty: {difficulty}.\n\nFULL TRANSCRIPT:\n\n{transcript}\n\n"
        f"Produce the complete evaluation."
    )
    r = _client().messages.create(
        model="claude-sonnet-4-6", max_tokens=3000,
        system=system, messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text.strip()


# ════════════════════════════════════════════════════════════════════
# VIEWS
# ════════════════════════════════════════════════════════════════════

def show_gate_view():
    """Landing page: login / create account."""

    # If user just came back from payment, auto-redirect to app
    if st.query_params.get("payment_success"):
        email = st.query_params.get("user_email", "")
        if email:
            credits = get_credits(email)
            st.session_state.current_user = {
                "uid": "",
                "email": email,
                "paid_interviews": credits,
            }
            st.query_params.clear()
            st.rerun()

    _, lang_col, _ = st.columns([2, 3, 2])
    with lang_col:
        _lang_selector(key_suffix="_gate")

    st.write("")
    st.markdown('<div class="app-title">OfferRoom</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitle">{t("subtitle")}</div>', unsafe_allow_html=True)
    st.divider()

    _, col, _ = st.columns([1, 3, 1])
    with col:
        c1, c2 = st.columns(2, gap="small")
        if c1.button(t("gate_create"), type="primary", use_container_width=True, key="gate_create_btn"):
            st.session_state.auth_mode = "signup"
            st.rerun()
        if c2.button(t("gate_login"), use_container_width=True, key="gate_login_btn"):
            st.session_state.auth_mode = "login"
            st.rerun()

        st.write("")
        st.divider()

        st.markdown(f"**{t('gate_new')}**")
        st.caption(t("gate_new_desc"))
        st.write("")
        st.markdown(f"**{t('gate_existing')}**")
        st.caption(t("gate_existing_desc"))

    if st.session_state.get("payment_message"):
        _pm = st.session_state.payment_message
        st.markdown(f'<div style="background:#f3e8ff;border-left:4px solid #6d28d9;border-radius:6px;padding:0.75rem 1rem;margin:0.5rem 0;color:#4c1d95;font-weight:500;">✓ {_pm}</div>', unsafe_allow_html=True)
        st.session_state.payment_message = None


def show_auth_view():
    """Login / signup form."""
    st.markdown("""
<style>
    input { border-color: #d1d5db !important; }
    input:focus { border-color: #9D00FF !important; box-shadow: 0 0 0 3px rgba(157,0,255,0.1) !important; }
    [data-testid="stFormSubmitButton"] button { background-color: #9D00FF !important; color: white !important; border: none !important; }
    [data-testid="stFormSubmitButton"] button:hover { background-color: #7c3aed !important; }
</style>
""", unsafe_allow_html=True)
    back_col, _, lang_col = st.columns([2, 3, 2])
    with back_col:
        if st.button(t("auth_back"), key="auth_back_btn"):
            st.session_state.auth_mode = False
            st.rerun()
    with lang_col:
        _lang_selector(key_suffix="_auth")

    st.write("")
    st.markdown('<div class="app-title">OfferRoom</div>', unsafe_allow_html=True)
    st.divider()

    _, col, _ = st.columns([1, 2, 1])
    with col:
        # Default tab based on how we got here
        default_idx = 0 if st.session_state.get("auth_mode") == "signup" else 1
        mode = st.selectbox(
            "auth_type",
            [t("auth_signup"), t("auth_login")],
            index=default_idx,
            label_visibility="collapsed",
            key="auth_type_radio",
        )
        st.write("")

        if mode == t("auth_signup"):
            with st.form("signup_form"):
                email_s = st.text_input(t("auth_email_lbl"), placeholder=t("auth_email_ph"), key="su_email")
                password_s = st.text_input(t("auth_password_lbl"), type="password", placeholder=t("auth_password_ph"), key="su_pw")
                confirm_s = st.text_input(t("auth_confirm_lbl"), type="password", placeholder=t("auth_confirm_ph"), key="su_confirm")
                if st.form_submit_button(t("auth_signup_btn"), type="primary", use_container_width=True):
                    ok, msg = signup_user(email_s, password_s, confirm_s)
                    if ok:
                        st.session_state.auth_mode = False
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            with st.form("login_form"):
                email = st.text_input(t("auth_email_lbl"), placeholder=t("auth_email_ph"), key="li_email")
                password = st.text_input(t("auth_password_lbl"), type="password", placeholder=t("auth_password_ph"), key="li_pw")
                if st.form_submit_button(t("auth_login_btn"), type="primary", use_container_width=True):
                    ok, msg = login_user(email, password)
                    if ok:
                        st.session_state.auth_mode = False
                        st.rerun()
                    else:
                        st.error(msg)


def _render_buy_options(user_email: str):
    """Inline buy buttons + Stripe redirect."""
    st.markdown(f"**{t('buy_title')}**")
    pkg_cols = st.columns(3)
    for i, (pkg_id, label_key, n_credits) in enumerate(CREDIT_PACKAGES):
        if pkg_cols[i].button(t(label_key), key=f"buy_{pkg_id}_inline", use_container_width=True):
            price_id = _get_price_id_for_package(pkg_id)
            if price_id and STRIPE_AVAILABLE:
                with st.spinner("…"):
                    try:
                        url = create_checkout_session(price_id, user_email, n_credits)
                        st.session_state.checkout_url = url
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            else:
                st.error("Payment not configured.")

    if st.session_state.get("checkout_url"):
        url = st.session_state.checkout_url
        st.markdown(
            f'<a href="{url}" style="display:block;text-align:center;background:#635bff;'
            f'color:white;padding:0.5rem 1rem;border-radius:8px;text-decoration:none;'
            f'font-weight:600;margin:0.5rem 0;">{t("sidebar_pay_now")}</a>',
            unsafe_allow_html=True,
        )
        import streamlit.components.v1 as components
        components.html(f'<script>window.top.location.href = "{url}";</script>', height=0)
        if st.button(t("sidebar_pay_cancel"), key="cancel_pay_inline"):
            st.session_state.checkout_url = None
            st.rerun()


def handle_api_error(err_str: str, user=None):
    """Show a friendly error card for API failures.

    If the error looks like an out-of-interviews error (credit balance exhausted
    on the Anthropic side), show a buy-more card. Otherwise show a trimmed raw
    error message.
    """
    lower = err_str.lower()
    if "credit balance" in lower or "out of interview" in lower or "insufficient" in lower:
        st.error(
            f"**{t('err_out_of_interviews')}**\n\n{t('err_out_of_interviews_msg')}"
        )
        if user:
            _render_buy_options(user["email"])
    else:
        st.error(err_str[:400] if len(err_str) > 400 else err_str)


def show_history_view():
    """Interview history dashboard."""
    user = st.session_state.current_user

    col_back, _, col_lang = st.columns([2, 4, 2])
    with col_back:
        if st.button(t("history_back"), key="hist_back_btn"):
            st.session_state.view = "setup"
            st.rerun()
    with col_lang:
        _lang_selector(key_suffix="_hist")

    st.divider()
    st.markdown(f"## {t('history_title')}")
    st.write("")

    with st.spinner(t("history_loading")):
        interviews = get_user_interviews(user["email"])

    if not interviews:
        st.info(t("history_no_interviews"))
        return

    # Summary metrics
    scores = [i["final_score"] for i in interviews if i.get("final_score")]
    avg = sum(scores) / len(scores) if scores else 0
    col1, col2, col3 = st.columns(3)
    col1.metric(t("history_total"), len(interviews))
    col2.metric(t("history_avg"), f"{avg:.1f} / 5")
    col3.metric(t("history_best"), f"{max(scores):.1f} / 5" if scores else "—")

    st.divider()

    for iv in interviews:
        raw_date = iv.get("date")
        date_str = raw_date.strftime("%b %d, %Y") if hasattr(raw_date, "strftime") else str(raw_date)[:10]
        score = iv.get("final_score", 0)
        pct = score / 5
        if pct >= 0.8:
            c = "#7c3aed"
        elif pct >= 0.6:
            c = "#a78bfa"
        else:
            c = "#d946ef"

        with st.expander(f"{date_str}  ·  {iv.get('role', '—')}  ·  **{score:.1f} / 5**"):
            left, right = st.columns([3, 1])
            with left:
                st.markdown(f"**Interviewer:** {iv.get('interviewer', '—')}")
                st.markdown(f"**Difficulty:** {iv.get('difficulty', '—')}")
                if iv.get("feedback"):
                    st.markdown(f"**Hire decision:** {iv['feedback']}")
                dur = iv.get("duration_minutes")
                if dur:
                    st.caption(f"Duration: {dur:.0f} min")
            with right:
                st.markdown(
                    f'<div style="text-align:center;background:{c}18;border:1.5px solid {c}50;'
                    f'border-radius:12px;padding:0.8rem;">'
                    f'<div style="font-size:1.8rem;font-weight:800;color:{c};">{score:.1f}</div>'
                    f'<div style="font-size:0.75rem;color:#6b7280;">out of 5</div></div>',
                    unsafe_allow_html=True,
                )
            sub1, sub2, sub3 = st.columns(3)
            sub1.metric("Narrative", f"{iv.get('narrative_score', '—')}/5")
            sub2.metric("Technical", f"{iv.get('technical_depth', '—')}/5")
            sub3.metric("Logical", f"{iv.get('logical_thinking', '—')}/5")


def show_interview_view():
    lang = st.session_state.get("language", "en")

    def _go_back():
        stage = st.session_state.get("interview_stage", "not_started")
        if stage not in ("done", "not_started"):
            # Mid-interview: show confirmation instead of immediately abandoning
            st.session_state._abandon_confirm = True
            return
        # Completed or not started — go back normally
        st.session_state.interview_active = False
        st.session_state.interview_messages = []
        st.session_state.interview_questions = []
        st.session_state.interview_q_num = 0
        st.session_state.interview_stage = "not_started"
        st.session_state.interview_evaluation = None
        st.session_state.session_interview_started = False
        st.session_state.current_session_id = None
        st.session_state.session_match_count = 0

    interviewer  = st.session_state.get("interviewer", "")
    role_title   = st.session_state.get("role_title", "")
    seniority    = st.session_state.get("seniority", "")
    difficulty   = st.session_state.get("difficulty", "Realistic")
    _iv_emoji, _iv_name = PERSONA_META.get(interviewer, ("👤", interviewer))

    # Header: back button + timer
    start_time = st.session_state.get("interview_start_time") or time.time()
    elapsed = int(time.time() - start_time)
    mins, secs = elapsed // 60, elapsed % 60
    timer_text = f"{mins:02d}:{secs:02d}"

    col_back, _, col_timer = st.columns([1, 4, 1])
    with col_back:
        if st.button(t("btn_back"), key="iv_back"):
            _go_back()
            st.rerun()
    with col_timer:
        st.markdown(
            f'<div style="text-align:right;font-weight:600;color:#9D00FF;font-size:0.95rem;padding-top:0.4rem;">'
            f'{timer_text}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Abandon confirmation overlay
    if st.session_state.get("_abandon_confirm"):
        st.warning(
            f"**{t('interview_incomplete_warning')}**\n\n{t('interview_incomplete_desc')}"
        )
        c_resume, c_abandon = st.columns(2)
        if c_resume.button(t("interview_resume"), type="primary", use_container_width=True, key="iv_resume_btn"):
            st.session_state._abandon_confirm = False
            st.rerun()
        if c_abandon.button(t("interview_abandon"), use_container_width=True, key="iv_abandon_btn"):
            sid = st.session_state.get("current_session_id")
            if sid:
                mark_session_completed(sid, status="abandoned")
            st.session_state.interview_active = False
            st.session_state.interview_messages = []
            st.session_state.interview_questions = []
            st.session_state.interview_q_num = 0
            st.session_state.interview_stage = "not_started"
            st.session_state.interview_evaluation = None
            st.session_state.session_interview_started = False
            st.session_state.current_session_id = None
            st.session_state.session_match_count = 0
            st.session_state._abandon_confirm = False
            st.rerun()
        return

    # Context line
    st.markdown(
        f"**{_iv_name}** &nbsp;·&nbsp; {interviewer} &nbsp;·&nbsp; "
        f"{seniority} {role_title} &nbsp;·&nbsp; "
        f"<span style='color:#6b7280;'>{t(f'diff_{difficulty}')}</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Generate setup on first load
    if not st.session_state.interview_messages:
        with st.spinner(t("spin_interview")):
            try:
                _use_custom = st.session_state.get("use_custom_interviewer", False)
                setup = generate_interview_setup(
                    cv_analysis=st.session_state.cv_analysis,
                    role_title=role_title,
                    seniority=seniority,
                    company_summary=st.session_state.get("company_summary", ""),
                    job_description=st.session_state.get("job_description", ""),
                    interviewer=interviewer,
                    difficulty=difficulty,
                    language=lang,
                    custom_role=st.session_state.get("custom_interviewer_role", "") if _use_custom else "",
                    custom_context=st.session_state.get("custom_interviewer_context", "") if _use_custom else "",
                )
                st.session_state.interview_questions = setup["questions"]
                intro = setup["persona_intro"]
                first_q = setup["questions"][0]
                opening = f"{intro}\n\n---\n\n{t('q_label').format(n=1, total=5)} {first_q}"
                st.session_state.interview_messages = [{"role": "assistant", "content": opening}]
                st.session_state.interview_q_num = 0
                st.session_state.interview_stage = "pending_answer"
            except Exception as e:
                st.error(t("err_start").format(e=e))
                return

    # Progress dots
    q_num = st.session_state.interview_q_num
    stage = st.session_state.interview_stage
    total = 5
    completed = total if stage == "done" else q_num
    dot_html = ""
    for i in range(total):
        if i < completed:
            color, dot = "#7c3aed", "●"
        elif i == q_num and stage != "done":
            color, dot = "#9D00FF", "◉"
        else:
            color, dot = "#d1d5db", "●"
        dot_html += f'<span style="font-size:1.1rem;color:{color};margin-right:4px;">{dot}</span>'

    label = t("progress_done") if stage == "done" else t("progress_q").format(n=q_num + 1, total=total)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:0.5rem;">'
        f'{dot_html}<span style="font-size:0.8rem;color:#6b7280;font-weight:500;">{label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Chat history
    for msg in st.session_state.interview_messages:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar=_iv_emoji):
                st.markdown(f"**{_iv_name} — {interviewer}**")
                st.markdown(_safe(_strip_iv_prefix(msg["content"])))
        else:
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:0.65rem;margin:0.85rem 0;">'
                f'<div style="width:2.4rem;height:2.4rem;border-radius:0.4rem;background:transparent;'
                f'display:flex;align-items:center;justify-content:center;font-size:1.25rem;flex-shrink:0;">🟣</div>'
                f'<div style="background:#f3e8ff;border-radius:0.5rem;padding:0.6rem 0.9rem;'
                f'flex:1;line-height:1.6;color:#1e293b;">{_safe(msg["content"])}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Done state
    if stage == "done":
        st.markdown(f'<div style="background:#f3e8ff;border-left:4px solid #6d28d9;border-radius:6px;padding:0.75rem 1rem;margin:0.5rem 0;color:#4c1d95;font-weight:500;">✓ {t("interview_complete")}</div>', unsafe_allow_html=True)
        st.write("")

        if st.session_state.interview_evaluation is None:
            if st.button(t("btn_get_eval"), type="primary", use_container_width=True):
                with st.spinner(t("spin_eval")):
                    try:
                        eval_text = generate_evaluation(
                            messages=st.session_state.interview_messages,
                            role_title=role_title,
                            seniority=seniority,
                            interviewer=interviewer,
                            difficulty=difficulty,
                            language=lang,
                        )
                        st.session_state.interview_evaluation = eval_text
                        # Auto-save for logged-in users
                        user = st.session_state.get("current_user")
                        if user:
                            start = st.session_state.get("interview_start_time", time.time())
                            duration = (time.time() - start) / 60
                            save_interview(user, role_title, seniority, interviewer, difficulty, eval_text, duration)
                        # Mark session completed
                        _sid = st.session_state.get("current_session_id")
                        if _sid:
                            mark_session_completed(_sid, status="completed")
                    except Exception as e:
                        st.error(t("err_eval").format(e=e))
                st.rerun()
        else:
            eval_text = st.session_state.interview_evaluation

            # ── Score header ───────────────────────────────────────────────────
            score_line = ""
            for line in eval_text.splitlines():
                if line.startswith("FINAL SCORE"):
                    score_line = line.split(":", 1)[-1].strip()
                    break
            if score_line:
                try:
                    score_val = float(score_line.split("/")[0].strip())
                    pct = score_val / 5
                    bar_color = "#7c3aed" if pct >= 0.8 else "#a78bfa" if pct >= 0.6 else "#d946ef"
                    st.markdown(
                        f'<div style="background:{bar_color}18;border:1.5px solid {bar_color}50;'
                        f'border-radius:12px;padding:1rem 1.5rem;margin-bottom:1rem;">'
                        f'<span style="font-size:2rem;font-weight:800;color:{bar_color};">{score_line}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                except ValueError:
                    pass

            # ── Quick stats: category breakdown ───────────────────────────────
            cat_scores = {"narrative": 0, "technical": 0, "logical": 0}
            for line in eval_text.splitlines():
                try:
                    if "Narrative:" in line and "/5" in line:
                        cat_scores["narrative"] = int(line.split(":", 1)[1].strip().split("/")[0].strip())
                    elif "Technical Depth:" in line and "/5" in line:
                        cat_scores["technical"] = int(line.split(":", 1)[1].strip().split("/")[0].strip())
                    elif "Logical Thinking:" in line and "/5" in line:
                        cat_scores["logical"] = int(line.split(":", 1)[1].strip().split("/")[0].strip())
                except (ValueError, IndexError):
                    pass

            def _score_color(s):
                return "#7c3aed" if s >= 4 else "#a78bfa" if s >= 3 else "#d946ef"

            if any(v > 0 for v in cat_scores.values()):
                st.markdown(f"### {t('stats_performance')}")
                sc1, sc2, sc3 = st.columns(3)
                for col, key, label in [
                    (sc1, "narrative",  t("stats_narrative")),
                    (sc2, "technical",  t("stats_technical")),
                    (sc3, "logical",    t("stats_logical")),
                ]:
                    sc = cat_scores[key]
                    c = _score_color(sc)
                    col.markdown(
                        f'<div style="background:{c}18;border:1.5px solid {c}50;'
                        f'border-radius:8px;padding:0.75rem;text-align:center;">'
                        f'<div style="font-size:0.8rem;color:#6b7280;font-weight:500;">{label}</div>'
                        f'<div style="font-size:1.8rem;font-weight:800;color:{c};">{sc}/5</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                st.write("")

                # ── Strength / weakness highlight ─────────────────────────────
                label_map = {
                    "narrative": t("stats_narrative"),
                    "technical": t("stats_technical"),
                    "logical":   t("stats_logical"),
                }
                best_key  = max(cat_scores, key=cat_scores.get)
                worst_key = min(cat_scores, key=cat_scores.get)

                sw1, sw2 = st.columns(2)
                sw1.markdown(
                    f'<div style="background:#ede9fe;border:1.5px solid #6d28d9;'
                    f'border-radius:8px;padding:1rem;">'
                    f'<div style="color:#4c1d95;font-weight:600;margin-bottom:0.4rem;">{t("stats_strength")}</div>'
                    f'<div style="color:#4c1d95;font-size:0.9rem;">{label_map[best_key]}</div>'
                    f'<div style="color:#6d28d9;font-weight:700;font-size:1.3rem;margin-top:0.4rem;">{cat_scores[best_key]}/5</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                sw2.markdown(
                    f'<div style="background:#f1f5f9;border:1.5px solid #1e293b;'
                    f'border-radius:8px;padding:1rem;">'
                    f'<div style="color:#1e293b;font-weight:600;margin-bottom:0.4rem;">{t("stats_weakness")}</div>'
                    f'<div style="color:#334155;font-size:0.9rem;">{label_map[worst_key]}</div>'
                    f'<div style="color:#1e293b;font-weight:700;font-size:1.3rem;margin-top:0.4rem;">{cat_scores[worst_key]}/5</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                st.write("")
                st.divider()

            # ── Full evaluation text ───────────────────────────────────────────
            st.markdown(_safe(eval_text))
            st.write("")

            # Post-eval usage info for credit users
            user = st.session_state.get("current_user")
            if user and not _DEV_MODE:
                remaining = user.get("paid_interviews", 0)
                st.info(t("post_eval_used").format(n=remaining))
                if remaining <= 2:
                    st.warning(t("post_eval_low"))
                    _render_buy_options(user["email"])

            # ── Share section ──────────────────────────────────────────────────
            st.write("")
            st.divider()
            st.markdown(f"### {t('share_title')}")

            # Build share text
            _share_score = 0.0
            try:
                for _ln in eval_text.splitlines():
                    if _ln.startswith("FINAL SCORE"):
                        _share_score = float(_ln.split(":", 1)[1].strip().split("/")[0].strip())
                        break
            except (ValueError, IndexError):
                pass

            # Use full "Seniority Role" label; fall back to custom role name if set
            if st.session_state.get("use_custom_interviewer"):
                _role_display = st.session_state.get("custom_interviewer_role") or role_title
            else:
                _role_display = f"{seniority} {role_title}".strip()

            _app_url = "https://offer-room.streamlit.app"
            share_text = (
                f"I just completed an interview prep with OfferRoom! 🎤\n\n"
                f"Role: {_role_display}\n"
                f"Interviewer: {interviewer}\n"
                f"Difficulty: {difficulty}\n"
                f"Score: {_share_score}/5\n\n"
                f"Ready to ace your next interview? Try OfferRoom free at {_app_url}"
            )
            _enc  = urllib.parse.quote(share_text, safe="")
            _eurl = urllib.parse.quote(_app_url, safe="")

            twitter_url  = f"https://twitter.com/intent/tweet?text={_enc}"
            linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={_eurl}"
            whatsapp_url = f"https://wa.me/?text={_enc}"

            # Info card
            st.markdown(
                f'<div style="background:#f3f4f6;border:1.5px solid #9D00FF40;'
                f'border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:1rem;">'
                f'<div style="font-weight:600;color:#9D00FF;margin-bottom:0.75rem;">{t("share_card_title")}</div>'
                f'<div style="font-size:0.9rem;color:#374151;line-height:1.7;">'
                f'<strong>{t("share_role")}:</strong> {_role_display}<br>'
                f'<strong>{t("share_interviewer")}:</strong> {interviewer}<br>'
                f'<strong>{t("share_score")}:</strong> {_share_score}/5'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # JS clipboard helper (injected once, idempotent)
            _js_share = json.dumps(share_text)  # properly escaped JS string literal
            st.markdown(
                f"""<script>
                function _orCopy(){{
                    var t={_js_share};
                    if(navigator.clipboard&&navigator.clipboard.writeText){{
                        navigator.clipboard.writeText(t).then(function(){{alert('Copied!');}});
                    }}else{{
                        var ta=document.createElement('textarea');
                        ta.value=t;document.body.appendChild(ta);ta.select();
                        document.execCommand('copy');document.body.removeChild(ta);
                        alert('Copied!');
                    }}
                }}
                </script>""",
                unsafe_allow_html=True,
            )

            # Share buttons
            sh1, sh2, sh3, sh4 = st.columns(4)
            btn_style = (
                "display:block;padding:0.65rem 0.5rem;border-radius:6px;"
                "text-decoration:none;font-weight:600;text-align:center;font-size:0.85rem;"
            )
            sh1.markdown(
                f'<a href="{twitter_url}" target="_blank" '
                f'style="{btn_style}background:#1DA1F2;color:white;">{t("share_twitter")}</a>',
                unsafe_allow_html=True,
            )
            sh2.markdown(
                f'<a href="{linkedin_url}" target="_blank" '
                f'style="{btn_style}background:#0A66C2;color:white;">{t("share_linkedin")}</a>',
                unsafe_allow_html=True,
            )
            sh3.markdown(
                f'<a href="{whatsapp_url}" target="_blank" '
                f'style="{btn_style}background:#25D366;color:white;">{t("share_whatsapp")}</a>',
                unsafe_allow_html=True,
            )
            sh4.markdown(
                f'<button onclick="_orCopy()" '
                f'style="width:100%;{btn_style}background:#6b7280;color:white;border:none;cursor:pointer;">'
                f'{t("share_copy")}</button>',
                unsafe_allow_html=True,
            )

            st.write("")
            st.caption(t("share_caption"))

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t("interview_practice_again"), use_container_width=True, type="primary", key="practice_again_btn"):
                # Reset interview state — keep CV/role/company/match so user goes straight to
                # interviewer+difficulty selection with the same context
                st.session_state.interview_active = False
                st.session_state.interview_messages = []
                st.session_state.interview_questions = []
                st.session_state.interview_q_num = 0
                st.session_state.interview_stage = "not_started"
                st.session_state.interview_evaluation = None
                st.session_state.session_interview_started = False
                st.session_state.current_session_id = None
                st.session_state.session_match_count = 0
                st.session_state.voice_mode = False
                # Reset interviewer/difficulty so user can pick fresh ones
                st.session_state.interviewer = ""
                st.session_state.difficulty = "Realistic"
                st.rerun()
        with col2:
            if st.button(t("interview_try_different"), use_container_width=True, key="try_different_btn"):
                # Full reset — blank slate
                st.session_state.interview_active = False
                st.session_state.interview_messages = []
                st.session_state.interview_questions = []
                st.session_state.interview_q_num = 0
                st.session_state.interview_stage = "not_started"
                st.session_state.interview_evaluation = None
                st.session_state.match_result = None
                st.session_state.cv_analysis = None
                st.session_state.cv_filename = None
                st.session_state.role_title = ""
                st.session_state.seniority = "Mid"
                st.session_state.company_summary = ""
                st.session_state.job_description = ""
                st.session_state.interviewer = ""
                st.session_state.difficulty = "Realistic"
                st.session_state.session_interview_started = False
                st.session_state.current_session_id = None
                st.session_state.session_match_count = 0
                st.session_state.use_custom_interviewer = False
                st.session_state.custom_interviewer_role = ""
                st.session_state.custom_interviewer_context = ""
                st.session_state.voice_mode = False
                st.rerun()
        return

    # ── Input area (voice or text) ────────────────────────────────────────────
    user_input = None
    voice_mode = st.session_state.get("voice_mode", False)

    if voice_mode:
        # Voice mode: recorder fills the row; keyboard icon sits to the right
        _c_rec, _c_kb = st.columns([10, 1])
        with _c_kb:
            if st.button("⌨️", key="voice_toggle_btn", help=t("voice_toggle_text")):
                st.session_state.voice_mode = False
                st.rerun()
        voice_comp = _get_voice_component()
        if voice_comp is not None:
            lang_code = {"en": "en-US", "es": "es-ES", "pt": "pt-BR"}.get(lang, "en-US")
            transcript = voice_comp(
                lang=lang_code,
                key=f"vc_{q_num}_{stage}",
                default=None,
            )
            if transcript:
                user_input = transcript
        else:
            st.warning(t("voice_unavailable"))
    else:
        # Text mode: chat input + mic button side-by-side (WhatsApp-style)
        _c_chat, _c_mic = st.columns([11, 1])
        with _c_chat:
            if typed := st.chat_input(t("chat_placeholder")):
                user_input = typed
        with _c_mic:
            if st.button("🎤", key="voice_toggle_btn", help=t("voice_toggle_mic")):
                st.session_state.voice_mode = True
                st.rerun()

    # ── Process the answer (identical for voice and typed input) ──────────────
    if user_input:
        st.session_state.interview_messages.append({"role": "user", "content": user_input})
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:0.65rem;margin:0.25rem 0;">'
            f'<div style="width:2.4rem;height:2.4rem;border-radius:0.4rem;background:#f0f2f6;'
            f'display:flex;align-items:center;justify-content:center;font-size:1.25rem;flex-shrink:0;">🟣</div>'
            f'<div style="background:#f3e8ff;border-radius:0.5rem;padding:0.6rem 0.9rem;'
            f'flex:1;line-height:1.6;color:#1e293b;">{_safe(user_input)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if stage == "pending_answer":
            base_q = st.session_state.interview_questions[q_num]
            with st.chat_message("assistant", avatar=_iv_emoji):
                st.markdown(f"**{_iv_name} — {interviewer}**")
                followup = _stream_safe(_stream_followup(
                    base_question=base_q, user_answer=user_input,
                    interviewer=interviewer, difficulty=difficulty,
                    role_title=role_title, seniority=seniority,
                    company_summary=st.session_state.get("company_summary", ""),
                    job_description=st.session_state.get("job_description", ""),
                    language=lang,
                ))
            st.session_state.interview_messages.append({"role": "assistant", "content": followup})
            st.session_state.interview_stage = "pending_followup_answer"

        elif stage == "pending_followup_answer":
            next_q_num = q_num + 1
            if next_q_num < total:
                next_q = st.session_state.interview_questions[next_q_num]
                next_msg = f"{t('q_label').format(n=next_q_num + 1, total=total)} {next_q}"
                with st.chat_message("assistant", avatar=_iv_emoji):
                    st.markdown(f"**{_iv_name} — {interviewer}**")
                    st.markdown(next_msg)
                st.session_state.interview_messages.append({"role": "assistant", "content": next_msg})
                st.session_state.interview_q_num = next_q_num
                st.session_state.interview_stage = "pending_answer"
            else:
                with st.chat_message("assistant", avatar=_iv_emoji):
                    st.markdown(f"**{_iv_name} — {interviewer}**")
                    closing = _stream_safe(_stream_closing(
                        interviewer=interviewer, role_title=role_title,
                        seniority=seniority, language=lang,
                    ))
                st.session_state.interview_messages.append({"role": "assistant", "content": closing})
                st.session_state.interview_stage = "done"

        st.rerun()


def show_setup_view():
    """Main setup page after authentication."""
    lang = st.session_state.get("language", "en")
    user = st.session_state.get("current_user")

    # ── Account bar: single flat row ─────────────────────────────────────────
    # [Language ▾] ··· email · credits  [History][Log out]
    c_lang, c_info, c_btn1, c_btn2 = st.columns([2, 3, 2, 2])

    with c_lang:
        _lang_selector(key_suffix="_setup")

    if _DEV_MODE:
        c_info.markdown(
            f'<p style="text-align:right;margin:0.3rem 0 0;">'
            f'<span style="background:#fbbf24;color:#000;border-radius:6px;'
            f'padding:2px 8px;font-size:0.75rem;font-weight:700;">{t("dev_badge")}</span></p>',
            unsafe_allow_html=True,
        )
    elif user:
        n_left = user.get("paid_interviews", 0)
        _cr = "#9D00FF" if n_left == 0 else "#7c3aed" if n_left <= 2 else "#6b7280"
        credits_html = (
            f'<span style="color:{_cr};font-weight:600;">'
            f'{t("acct_credits").format(n=n_left)}</span>'
        )
        c_info.markdown(
            f'<p style="text-align:right;font-size:0.8rem;margin:0.3rem 0 0;line-height:1.5;">'
            f'<span style="color:#6b7280;">{user["email"]}</span><br>{credits_html}</p>',
            unsafe_allow_html=True,
        )
        if c_btn1.button(t("acct_history"), key="setup_history_btn", use_container_width=True):
            st.session_state.view = "history"
            st.rerun()
        if c_btn2.button(t("acct_logout_btn"), key="setup_logout_btn", use_container_width=True):
            logout_user()
            st.rerun()
    st.divider()

    # Payment message
    if st.session_state.get("payment_message"):
        _pm = st.session_state.payment_message
        st.markdown(f'<div style="background:#f3e8ff;border-left:4px solid #6d28d9;border-radius:6px;padding:0.75rem 1rem;margin:0.5rem 0;color:#4c1d95;font-weight:500;">✓ {_pm}</div>', unsafe_allow_html=True)
        st.session_state.payment_message = None

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown('<div class="app-title">OfferRoom</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-subtitle">{t("subtitle")}</div>', unsafe_allow_html=True)
    st.divider()

    # ── CV upload / saved CVs ─────────────────────────────────────────────────
    st.markdown(f'<div class="lbl">{t("lbl_cv")}</div>', unsafe_allow_html=True)

    if user:
        # Lazy-load saved CVs
        if st.session_state.get("saved_cvs") is None:
            st.session_state.saved_cvs = get_user_cvs(user["email"])
        saved_cvs = st.session_state.saved_cvs or []

        if saved_cvs:
            # ── Saved CVs dropdown ────────────────────────────────────────────
            upload_option = t("cv_upload_new")
            options = [cv["filename"] for cv in saved_cvs] + [upload_option]
            selected_cv = st.selectbox(
                "cv_select", options,
                index=len(options) - 1,
                label_visibility="collapsed",
                key="cv_select",
            )

            if selected_cv != upload_option:
                # Load from cache — zero Claude calls, create session
                chosen = next((cv for cv in saved_cvs if cv["filename"] == selected_cv), None)
                if chosen:
                    if st.session_state.cv_filename != chosen["filename"]:
                        cached = chosen.get("cv_analysis") or chosen.get("cv_text")
                        st.session_state.cv_analysis = cached
                        st.session_state.cv_filename = chosen["filename"]
                        st.session_state.match_result = None
                        st.session_state.session_match_count = 0
                        if not _DEV_MODE:
                            sid = create_interview_session_from_saved(
                                user["email"], chosen["filename"],
                                chosen.get("cv_analysis") or {},
                            )
                            st.session_state.current_session_id = sid
                    has_cache = bool(chosen.get("cv_analysis"))
                    c_cv, c_del = st.columns([5, 1.5])
                    c_cv.caption(
                        t("cv_cached_ok") + f" · {chosen['filename']}"
                        if has_cache else f"✓ {chosen['filename']}"
                    )
                    if c_del.button(t("cv_delete"), key="del_selected_cv", use_container_width=True):
                        delete_cv(chosen["id"])
                        if st.session_state.cv_filename == chosen["filename"]:
                            st.session_state.cv_analysis = None
                            st.session_state.cv_filename = None
                            st.session_state.match_result = None
                            st.session_state.current_session_id = None
                            st.session_state.session_match_count = 0
                        st.session_state.saved_cvs = None
                        st.rerun()
            else:
                # "Upload new CV" selected
                if len(saved_cvs) >= _MAX_CVS:
                    st.warning(t("cv_limit_warn"))
                    for cv in saved_cvs:
                        c1, c2 = st.columns([5, 1.5])
                        c1.caption(cv["filename"])
                        if c2.button(t("cv_delete"), key=f"del_cv_{cv['id']}"):
                            delete_cv(cv["id"])
                            if st.session_state.cv_filename == cv["filename"]:
                                st.session_state.cv_analysis = None
                                st.session_state.cv_filename = None
                                st.session_state.match_result = None
                                st.session_state.current_session_id = None
                                st.session_state.session_match_count = 0
                            st.session_state.saved_cvs = None
                            st.rerun()
                else:
                    cv_file = st.file_uploader("CV", type=["pdf", "doc", "docx"], label_visibility="collapsed")
                    if cv_file and cv_file.name != st.session_state.cv_filename:
                        _has_interviews = user.get("paid_interviews", 0) > 0
                        if not (_has_interviews or _DEV_MODE):
                            st.error(t("err_cv_no_access"))
                            _render_buy_options(user["email"])
                        else:
                            if not _DEV_MODE:
                                st.info(
                                    f"📌 **New interview session**\n\n"
                                    f"With this CV you can score against up to 3 roles, "
                                    f"then run 1 interview.\n\n"
                                    f"**Token is deducted when you START the interview, not now.**\n\n"
                                    f"You have **{user['paid_interviews']} interview(s)** remaining."
                                )
                            with st.spinner(t("spin_cv")):
                                try:
                                    raw_text = extract_cv_text(cv_file)
                                    if raw_text:
                                        analysis = analyze_cv(raw_text)
                                        st.session_state.cv_analysis = analysis
                                        st.session_state.cv_filename = cv_file.name
                                        st.session_state.match_result = None
                                        st.session_state.session_match_count = 0
                                        ok, _ = save_cv_to_firebase(
                                            user["email"], cv_file.name,
                                            raw_text, cv_analysis=analysis,
                                        )
                                        if ok:
                                            st.session_state.saved_cvs = None
                                        if not _DEV_MODE:
                                            sid = create_interview_session(
                                                user["email"], cv_file.name,
                                                raw_text, analysis,
                                            )
                                            st.session_state.current_session_id = sid
                                        st.markdown(f'<div style="background:#f3e8ff;border-left:4px solid #6d28d9;border-radius:6px;padding:0.75rem 1rem;margin:0.5rem 0;color:#4c1d95;font-weight:500;">{t("cv_saved_ok")}</div>', unsafe_allow_html=True)
                                except Exception as e:
                                    st.error(t("err_cv").format(e=e))
        else:
            # ── No saved CVs: plain uploader ──────────────────────────────────
            cv_file = st.file_uploader("CV", type=["pdf", "doc", "docx"], label_visibility="collapsed")
            if cv_file and cv_file.name != st.session_state.cv_filename:
                _has_interviews = user.get("paid_interviews", 0) > 0
                if not (_has_interviews or _DEV_MODE):
                    st.error(t("err_cv_no_access"))
                    _render_buy_options(user["email"])
                else:
                    if not _DEV_MODE:
                        st.info(
                            f"📌 **New interview session**\n\n"
                            f"With this CV you can score against up to 3 roles, "
                            f"then run 1 interview.\n\n"
                            f"**Token is deducted when you START the interview, not now.**\n\n"
                            f"You have **{user['paid_interviews']} interview(s)** remaining."
                        )
                    with st.spinner(t("spin_cv")):
                        try:
                            raw_text = extract_cv_text(cv_file)
                            if raw_text:
                                analysis = analyze_cv(raw_text)
                                st.session_state.cv_analysis = analysis
                                st.session_state.cv_filename = cv_file.name
                                st.session_state.match_result = None
                                st.session_state.session_match_count = 0
                                ok, _ = save_cv_to_firebase(
                                    user["email"], cv_file.name,
                                    raw_text, cv_analysis=analysis,
                                )
                                if ok:
                                    st.session_state.saved_cvs = None
                                if not _DEV_MODE:
                                    sid = create_interview_session(
                                        user["email"], cv_file.name,
                                        raw_text, analysis,
                                    )
                                    st.session_state.current_session_id = sid
                                st.markdown(f'<div style="background:#f3e8ff;border-left:4px solid #6d28d9;border-radius:6px;padding:0.75rem 1rem;margin:0.5rem 0;color:#4c1d95;font-weight:500;">{t("cv_saved_ok")}</div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(t("err_cv").format(e=e))

    st.write("")

    # ── Role + Seniority ──────────────────────────────────────────────────────
    col_r, col_s = st.columns([2, 1])
    with col_r:
        st.markdown(f'<div class="lbl">{t("lbl_role")}</div>', unsafe_allow_html=True)
        role_title = st.text_input("role", placeholder=t("ph_role"), label_visibility="collapsed")
    with col_s:
        st.markdown(f'<div class="lbl">{t("lbl_seniority")}</div>', unsafe_allow_html=True)
        seniority = st.selectbox(
            "seniority",
            ["Associate", "Junior", "Mid", "Senior", "Principal", "Director", "Head", "VP", "C-Level"],
            label_visibility="collapsed",
        )

    st.write("")

    # ── Company ───────────────────────────────────────────────────────────────
    st.markdown(f'<div class="lbl">{t("lbl_company")}</div>', unsafe_allow_html=True)
    has_credits = _DEV_MODE or bool(user and user.get("paid_interviews", 0) > 0)
    col_u, col_e = st.columns([5, 1.5])
    with col_u:
        company_url = st.text_input("url", placeholder=t("ph_company_url"), label_visibility="collapsed")
    with col_e:
        can_fetch = bool(company_url.strip()) and has_credits
        if st.button(t("btn_evaluate"), disabled=not can_fetch, use_container_width=True, key="eval_btn"):
            url = company_url.strip()
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            with st.spinner(t("spin_company")):
                try:
                    summary = fetch_and_summarize(url)
                    if summary:
                        st.session_state.company_text = summary
                        st.session_state.match_result = None
                        st.rerun()
                except Exception as e:
                    err = str(e)
                    if any(x in err for x in ("No scheme", "Invalid URL", "invalid")):
                        st.error("❌ Invalid URL — try: https://company.com")
                    elif any(x in err for x in ("urlopen", "Connection", "timeout", "Name or service")):
                        st.error("❌ Could not reach that website. Check the URL and try again.")
                    else:
                        st.error("❌ Could not fetch company info. Try a different URL.")
    if company_url.strip() and not has_credits:
        st.caption("💳 Buy interview credits to fetch company details.")

    company_summary = st.text_area(
        "company_summary", placeholder=t("ph_company_text"),
        label_visibility="collapsed", height=90, key="company_text",
    )

    st.write("")

    # ── Job description ───────────────────────────────────────────────────────
    st.markdown(
        f'<div class="lbl">{t("lbl_jd")} '
        f'<span style="font-weight:400;color:#9ca3af;">({t("lbl_jd_optional")})</span></div>',
        unsafe_allow_html=True,
    )
    job_description = st.text_area(
        "jd", placeholder=t("ph_jd"), label_visibility="collapsed", height=90,
    )

    st.write("")
    st.divider()

    # ── Match score ───────────────────────────────────────────────────────────
    can_match = st.session_state.cv_analysis is not None and bool(role_title)
    match_btn = st.button(t("btn_match"), disabled=not can_match, use_container_width=True)

    if not can_match:
        missing = []
        if not st.session_state.cv_analysis:
            missing.append(t("enable_cv"))
        if not role_title:
            missing.append(t("enable_role"))
        st.caption(t("enable_hint").format(parts=" and ".join(missing)))

    if match_btn:
        with st.spinner(t("spin_match")):
            try:
                st.session_state.match_result = score_match(
                    st.session_state.cv_analysis, role_title, seniority,
                    company_summary or "", job_description or "",
                )
            except Exception as e:
                st.error(t("err_match").format(e=e))

    if st.session_state.match_result:
        r = st.session_state.match_result
        score = r["score"]
        COLORS = {1: "#d946ef", 2: "#d946ef", 3: "#a78bfa", 4: "#7c3aed", 5: "#7c3aed"}
        c = COLORS[score]
        dots = "".join(
            f'<span style="font-size:1.4rem;color:{c if i <= score else "#e5e7eb"};">●</span>'
            for i in range(1, 6)
        )
        st.markdown(f"""
<div class="score-box" style="background:{c}15;border:1.5px solid {c}50;">
  <div style="display:flex;align-items:baseline;gap:0.75rem;margin-bottom:0.4rem;">
    <span style="font-size:2.2rem;font-weight:800;color:{c};line-height:1;">{score}/5</span>
    <span style="font-size:1rem;font-weight:600;color:{c};">{t(f"match_{score}")}</span>
  </div>
  <div style="margin-bottom:0.6rem;letter-spacing:3px;">{dots}</div>
  <div style="font-size:0.92rem;color:#374151;line-height:1.6;">{r["explanation"]}</div>
</div>
""", unsafe_allow_html=True)

    # ── Phase 2: Interviewer + Difficulty + Start ─────────────────────────────
    if st.session_state.match_result:
        st.write("")
        st.divider()

        # ── Interviewer selector ──────────────────────────────────────────────
        st.markdown(f'<div class="lbl">{t("lbl_interviewer")}</div>', unsafe_allow_html=True)

        INTERVIEWERS = {k: v["subtitle"] for k, v in PERSONAS.items()
                        if k != "Custom Interviewer"}
        _custom_label = t("custom_role_title")
        interviewer_options = list(INTERVIEWERS.keys()) + [_custom_label]

        interviewer_choice = st.selectbox(
            "interviewer",
            interviewer_options,
            format_func=lambda k: k if k == _custom_label else f"{k}  —  {INTERVIEWERS[k]}",
            label_visibility="collapsed",
            key="interviewer_select",
        )

        if interviewer_choice == _custom_label:
            interviewer = "Custom Interviewer"
            st.session_state.use_custom_interviewer = True
            custom_role_input = st.text_input(
                "custom_role_input",
                placeholder=t("custom_role_ph"),
                label_visibility="collapsed",
                key="custom_role_text",
            )
            custom_context_input = st.text_area(
                "custom_context_input",
                placeholder=t("custom_role_context_ph"),
                label_visibility="collapsed",
                height=80,
                key="custom_role_ctx",
            )
            st.session_state.custom_interviewer_role = custom_role_input.strip()
            st.session_state.custom_interviewer_context = custom_context_input.strip()
        else:
            interviewer = interviewer_choice
            st.session_state.use_custom_interviewer = False

        st.write("")
        st.markdown(f'<div class="lbl">{t("lbl_difficulty")}</div>', unsafe_allow_html=True)
        LEVELS = ["Friendly", "Realistic", "Brutal"]
        diff_cols = st.columns(len(LEVELS))
        for i, (col, lvl) in enumerate(zip(diff_cols, LEVELS)):
            display = t(f"diff_{lvl}")
            label = f"**{display}**" if st.session_state.difficulty == lvl else display
            if col.button(label, key=f"diff_{i}", use_container_width=True):
                st.session_state.difficulty = lvl
                st.rerun()
        bar_cols = st.columns(len(LEVELS))
        for col, lvl in zip(bar_cols, LEVELS):
            active = st.session_state.difficulty == lvl
            col.markdown(
                f'<div style="height:4px;border-radius:2px;'
                f'background:{"#9D00FF" if active else "#e5e7eb"};margin-top:4px;"></div>',
                unsafe_allow_html=True,
            )

        # Difficulty description card
        _diff_desc = {
            "Friendly":  t("difficulty_friendly_desc"),
            "Realistic": t("difficulty_realistic_desc"),
            "Brutal":    t("difficulty_brutal_desc"),
        }
        _cur = st.session_state.difficulty
        st.markdown(
            f'<div style="border-left:3px solid #9D00FF;padding:0.75rem 1rem;'
            f'margin-top:0.5rem;color:#4b5563;font-size:0.9rem;line-height:1.6;">'
            f'{_diff_desc.get(_cur,"")}</div>',
            unsafe_allow_html=True,
        )

        st.write("")
        st.divider()

        # ── Access + start interview ──────────────────────────────────────────
        credits = user.get("paid_interviews", 0) if user else 0
        # Custom mode requires a role to be entered
        custom_ready = (not st.session_state.get("use_custom_interviewer") or
                        bool(st.session_state.get("custom_interviewer_role", "").strip()))
        can_start = (credits > 0 or _DEV_MODE) and custom_ready

        def _do_start():
            """Shared logic that fires the interview."""
            st.session_state.interview_start_time = time.time()
            st.session_state.session_interview_started = True
            st.session_state.update({
                "role_title": role_title,
                "seniority": seniority,
                "company_summary": company_summary or "",
                "job_description": job_description or "",
                "interviewer": interviewer,
                "difficulty": st.session_state.difficulty,
                "interview_active": True,
                "interview_messages": [],
                "interview_questions": [],
                "interview_q_num": 0,
                "interview_stage": "not_started",
                "interview_evaluation": None,
            })

        if not can_start and user and not custom_ready:
            st.caption("Enter a role for your custom interviewer above to continue.")

        if _DEV_MODE:
            if st.button(t("btn_start"), type="primary", use_container_width=True,
                         disabled=not can_start):
                _do_start()
                st.rerun()
        else:
            # Credit users — show cost warning + confirm/cancel
            if credits <= 0:
                st.warning(t("no_credits"))
                _render_buy_options(user["email"])
            else:
                after = max(0, credits - 1)
                st.warning(
                    f"⚠️ **Starting will use 1 of your {credits} interview(s).** "
                    f"You'll have {after} left. If you abandon mid-interview, the token is lost.",
                )
                c_start, c_cancel = st.columns(2)
                if c_start.button(t("btn_start"), type="primary", use_container_width=True,
                                  disabled=not can_start, key="start_confirmed"):
                    deduct_credit(user["email"])
                    st.session_state.current_user["paid_interviews"] = max(0, credits - 1)
                    session_id = st.session_state.get("current_session_id")
                    if session_id:
                        mark_session_token_reserved(session_id)
                    _do_start()
                    st.rerun()
                if c_cancel.button(t("sidebar_pay_cancel"), use_container_width=True, key="start_cancel"):
                    st.info("Interview cancelled.")


# ════════════════════════════════════════════════════════════════════
# PAGE SETUP
# ════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="OfferRoom", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    #MainMenu, footer, header { visibility: hidden; }
    [data-testid="collapsedControl"] { display: none; }
    .block-container { max-width: 720px; padding-top: 2rem; }

    .app-title {
        text-align: center;
        font-size: 3.5rem;
        font-weight: 800;
        letter-spacing: -1px;
        margin-bottom: 0.25rem;
        background: linear-gradient(135deg, #000 0%, #9D00FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .app-subtitle {
        text-align: center;
        font-size: 1.1rem;
        color: #6b7280;
        margin-bottom: 2.5rem;
    }
    .lbl {
        font-size: 0.8rem;
        font-weight: 600;
        color: #9D00FF;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.15rem;
    }
    .score-box {
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin: 0.75rem 0 0 0;
    }
    button[kind="primary"] { transition: box-shadow 0.2s ease; }
    button[kind="primary"]:hover { box-shadow: 0 4px 14px rgba(157, 0, 255, 0.25); }
    [role="radio"] { accent-color: #9D00FF !important; }

    /* ── Global purple overrides ── */
    .stButton > button {
        background-color: #9D00FF !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px rgba(157, 0, 255, 0.15) !important;
    }
    .stButton > button:hover {
        background-color: #7c3aed !important;
        box-shadow: 0 4px 16px rgba(157, 0, 255, 0.3) !important;
        transform: translateY(-2px) !important;
    }
    .stButton > button:active {
        background-color: #6d28d9 !important;
    }
    [role="radio"]:checked { accent-color: #7c3aed !important; }
    [type="checkbox"] { accent-color: #9D00FF !important; }
    [data-baseweb="select"] { --color-primary: #9D00FF !important; }
    input[type="radio"] {
        accent-color: #9D00FF !important;
        width: 18px !important;
        height: 18px !important;
        cursor: pointer !important;
    }
    input[type="radio"]:checked { accent-color: #7c3aed !important; }
    *[style*="accent-color: rgb(255"] { accent-color: #9D00FF !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ──────────────────────────────────────────────────────

for k, v in {
    "language": "en",
    "current_user": None,
    "auth_mode": False,
    "view": "setup",
    "payment_message": None,
    "checkout_url": None,
    "cv_analysis": None,
    "cv_filename": None,
    "match_result": None,
    "company_text": "",
    "difficulty": "Realistic",
    "interview_active": False,
    "interview_messages": [],
    "interview_questions": [],
    "interview_q_num": 0,
    "interview_stage": "not_started",
    "interview_evaluation": None,
    "interview_start_time": None,
    "saved_cvs": None,
    "voice_mode": False,
    "current_session_id": None,
    "session_match_count": 0,
    "session_interview_started": False,
    "use_custom_interviewer": False,
    "custom_interviewer_role": "",
    "custom_interviewer_context": "",
    "_abandon_confirm": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Language from URL query param (?lang=en/es/pt) ──────────────────────────────
_qp_lang = st.query_params.get("lang", "")
if _qp_lang in ("en", "es", "pt"):
    st.session_state.language = _qp_lang

# ── Dev mode: auto-login ────────────────────────────────────────────────────────

if _DEV_MODE and not st.session_state.current_user:
    st.session_state.current_user = {
        "uid": "dev-user",
        "email": "dev@offerroom.com",
        "paid_interviews": 9999,
    }

# ── Handle Stripe callback ──────────────────────────────────────────────────────

handle_payment_success()

# ── Auth gate ───────────────────────────────────────────────────────────────────

# Try to restore session from previous login
_load_user_from_session_cookie()

if not st.session_state.current_user:
    if st.session_state.auth_mode:
        show_auth_view()
    else:
        show_gate_view()
    st.stop()

# ── Routing ──────────────────────────────────────────────────────────────────────

if st.session_state.view == "history":
    show_history_view()
    st.stop()

if st.session_state.interview_active:
    show_interview_view()
    st.stop()

show_setup_view()
