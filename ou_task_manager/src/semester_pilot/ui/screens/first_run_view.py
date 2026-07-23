from html import escape

from semester_pilot.ui.components import alert, button, empty_state
from semester_pilot.ui.theme import DEFAULT_THEME_ASSETS, ThemeAssets
from semester_pilot.ui.view_models.first_run_models import FirstRunState, FirstRunStep


class FirstRunView:
    """Renders the first-run workflow from UI-ready state only."""

    def __init__(self, assets: ThemeAssets = DEFAULT_THEME_ASSETS) -> None:
        self._assets = assets

    def render(self, state: FirstRunState) -> str:
        return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#109b98">
  <title>{escape(state.title)} | SemesterPilot</title>
  <link rel="stylesheet" href="{escape(self._assets.stylesheet_url)}">
  <script src="{escape(self._assets.interaction_script_url)}" defer></script>
</head>
<body class="onboarding-body" data-workflow-step="{state.step.value}" data-busy="{str(state.is_busy).lower()}">
  <a class="skip-link" href="#main-content">דלגו לתוכן הראשי</a>
  <header class="onboarding-topbar">
    <a class="brand onboarding-brand" href="/" aria-label="SemesterPilot — דף פתיחה">
      <span class="brand__mark" aria-hidden="true">S</span>
      <span><strong>SemesterPilot</strong><small>לומדים בקצב שלך</small></span>
    </a>
    <span class="secure-note"><span aria-hidden="true">◇</span> הנתונים נשארים במחשב שלך</span>
  </header>
  <main id="main-content" class="onboarding-main" tabindex="-1">
    {self._step_indicator(state.step)}
    <section class="onboarding-panel" aria-labelledby="workflow-title">
      {self._content(state)}
    </section>
  </main>
</body>
</html>"""

    def _content(self, state: FirstRunState) -> str:
        if state.step is FirstRunStep.WELCOME:
            return self._welcome(state)
        if state.step in {FirstRunStep.LOADING, FirstRunStep.SYNCHRONIZING}:
            return self._loading(state)
        if state.step is FirstRunStep.PREVIEW:
            return self._preview(state)
        if state.step is FirstRunStep.SUCCESS:
            return self._success(state)
        if state.step is FirstRunStep.ERROR:
            return self._error(state)
        return self._dashboard(state)

    @staticmethod
    def _welcome(state: FirstRunState) -> str:
        return f"""
        <div class="welcome-layout">
          <div class="welcome-copy">
            <span class="welcome-icon" aria-hidden="true">✦</span>
            <p class="eyebrow">ברוכים הבאים</p>
            <h1 id="workflow-title">{escape(state.title)}</h1>
            <p class="welcome-lead">{escape(state.description)}</p>
            <ul class="welcome-benefits">
              <li><span aria-hidden="true">✓</span> כל המועדים במקום אחד</li>
              <li><span aria-hidden="true">✓</span> בדיקה לפני כל שינוי</li>
              <li><span aria-hidden="true">✓</span> מידע מקומי ופרטי</li>
            </ul>
          </div>
          <form class="file-card" data-file-form>
            <label for="calendar-file" class="file-dropzone">
              <span class="file-dropzone__icon" aria-hidden="true">ICS</span>
              <strong>בחרו את לוח השנה שלכם</strong>
              <span>קובץ ‎.ics שהורד מאתר האוניברסיטה הפתוחה</span>
              <span class="button button--primary" aria-hidden="true">בחירת קובץ</span>
            </label>
            <input class="sr-only" id="calendar-file" name="calendar" type="file" accept=".ics,text/calendar"
                   required data-file-input>
            <p class="file-help" id="file-help">הקובץ ייבדק לפני שיישמר מידע כלשהו.</p>
          </form>
        </div>"""

    @staticmethod
    def _loading(state: FirstRunState) -> str:
        return f"""
        <div class="workflow-centered" role="status" aria-live="polite" aria-busy="true">
          <div class="workflow-loader" aria-hidden="true"><span></span></div>
          <p class="eyebrow">תהליך מאובטח</p>
          <h1 id="workflow-title">{escape(state.title)}</h1>
          <p>{escape(state.description)}</p>
          <div class="workflow-progress" role="progressbar" aria-label="התקדמות הייבוא"
               aria-valuemin="0" aria-valuemax="100" aria-valuenow="{state.progress}">
            <span style="--progress: {state.progress}%"></span>
          </div>
          <p class="file-help">{escape(state.filename or "לוח שנה")}</p>
        </div>"""

    def _preview(self, state: FirstRunState) -> str:
        metrics = self._metrics(state)
        warnings = "".join(f"<li>{escape(warning)}</li>" for warning in state.warnings)
        warning_panel = (
            f"""<section class="workflow-warning" role="alert"><strong>כדאי לבדוק לפני שממשיכים</strong>
              <ul>{warnings}</ul></section>"""
            if warnings
            else alert("הקובץ עבר את בדיקות הבטיחות", "אפשר להמשיך לסנכרון. השינויים יישמרו יחד.", tone="success")
        )
        confirm = button(
            "אישור וסנכרון",
            attributes=("data-confirm-import" if state.can_confirm else 'disabled aria-disabled="true"'),
        )
        return f"""
        <div class="workflow-heading"><span class="welcome-icon welcome-icon--small" aria-hidden="true">✓</span>
          <div><p class="eyebrow">תצוגה מקדימה אמיתית</p><h1 id="workflow-title">{escape(state.title)}</h1>
          <p>{escape(state.description)}</p></div></div>
        <div class="selected-file"><span class="import-file__icon" aria-hidden="true">ICS</span>
          <span><strong>{escape(state.filename or "calendar.ics")}</strong><small>מוכן לאישור</small></span></div>
        <section aria-labelledby="preview-summary"><h2 id="preview-summary">מה ישתנה?</h2>
          <div class="metrics-grid workflow-metrics">{metrics}</div></section>
        {warning_panel}
        <div class="workflow-actions">{button("בחירת קובץ אחר", variant="secondary", attributes="data-reset-workflow")}
          {confirm}</div>"""

    def _success(self, state: FirstRunState) -> str:
        return f"""
        <div class="workflow-centered success-screen" role="status" aria-live="polite">
          <span class="success-mark" aria-hidden="true">✓</span>
          <p class="eyebrow">הסנכרון הושלם</p>
          <h1 id="workflow-title">{escape(state.title)}</h1>
          <p>{escape(state.description)}</p>
          <div class="success-total"><strong>{state.total_processed}</strong><span>אירועים יובאו</span></div>
          <div class="metrics-grid workflow-metrics success-metrics">{self._metrics(state, include_unsafe=False, completed=True)}</div>
          <p class="elapsed-time"><span aria-hidden="true">◷</span> זמן הסנכרון: {escape(state.elapsed_label or "פחות משנייה")}</p>
          {button("מעבר למרחב שלי", attributes="data-continue-dashboard")}
        </div>"""

    @staticmethod
    def _error(state: FirstRunState) -> str:
        return f"""
        <div class="workflow-centered error-screen">
          <span class="error-mark" aria-hidden="true">!</span>
          <p class="eyebrow">אפשר לנסות שוב</p>
          <h1 id="workflow-title">{escape(state.title)}</h1>
          <p>{escape(state.description)}</p>
          <section class="workflow-error" role="alert">{escape(state.error_message or "אירעה שגיאה לא צפויה.")}</section>
          {button("בחירת קובץ אחר", attributes="data-reset-workflow")}
        </div>"""

    @staticmethod
    def _dashboard(state: FirstRunState) -> str:
        return f"""
        <div class="workflow-centered dashboard-arrival">
          <span class="welcome-icon" aria-hidden="true">✦</span>
          <p class="eyebrow">הגעתם ל־SemesterPilot</p>
          <h1 id="workflow-title">{escape(state.title)}</h1>
          <p>{escape(state.description)}</p>
          {empty_state("לוח השנה מחובר", "המועדים שלך נשמרו. מסך הניהול המלא יגיע ב־Milestone 6.")}
        </div>"""

    @staticmethod
    def _metrics(state: FirstRunState, *, include_unsafe: bool = True, completed: bool = False) -> str:
        metrics = (
            state.metrics if include_unsafe else tuple(metric for metric in state.metrics if metric.key != "unsafe")
        )
        return "".join(
            f"""<div class="metric metric--{escape(metric.tone)}"><span>{escape("עודכנו" if completed and metric.key == "updated" else metric.label)}</span>
              <strong>{metric.value}</strong></div>"""
            for metric in metrics
        )

    @staticmethod
    def _step_indicator(step: FirstRunStep) -> str:
        positions = {
            FirstRunStep.WELCOME: 1,
            FirstRunStep.LOADING: 1,
            FirstRunStep.ERROR: 1,
            FirstRunStep.PREVIEW: 2,
            FirstRunStep.SYNCHRONIZING: 3,
            FirstRunStep.SUCCESS: 3,
            FirstRunStep.DASHBOARD: 3,
        }
        current = positions[step]
        labels = ("בחירת קובץ", "בדיקה ואישור", "סיום")
        items = "".join(
            f'<li class="{"is-current" if index == current else "is-complete" if index < current else ""}" '
            f"{'aria-current=step' if index == current else ''}><span>{index}</span>{label}</li>"
            for index, label in enumerate(labels, 1)
        )
        return f'<ol class="step-indicator" aria-label="שלבי הייבוא">{items}</ol>'
