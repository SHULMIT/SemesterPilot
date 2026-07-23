from html import escape

from semester_pilot.ui.components import (
    alert,
    assignment_card,
    badge,
    button,
    course_identity,
    dialog_shell,
    empty_state,
    loading_state,
    page_header,
    select_input,
    status_chip,
    text_input,
)
from semester_pilot.ui.view_models.models import CourseIdentityState, ImportPreviewState, PrototypePageState
from semester_pilot.ui.theme import DEFAULT_THEME_ASSETS, ThemeAssets


class PrototypeView:
    """Renders the isolated Milestone 4 web prototype from presentation state."""

    def __init__(self, assets: ThemeAssets = DEFAULT_THEME_ASSETS) -> None:
        self._assets = assets

    def render(self, state: PrototypePageState) -> str:
        return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#123b67">
  <title>{escape(state.page_title)} | SemesterPilot</title>
  <link rel="stylesheet" href="{escape(self._assets.stylesheet_url)}">
  <script src="{escape(self._assets.interaction_script_url)}" defer></script>
</head>
<body>
  <a class="skip-link" href="#main-content">דלגו לתוכן הראשי</a>
  <div class="app-shell">
    {self._sidebar(state)}
    <div class="app-frame">
      {self._topbar(state)}
      <main id="main-content" class="main-content" tabindex="-1">
        {page_header(state.page_eyebrow, state.page_title, state.page_description)}
        {self._notice(state.notice)}
        {self._content(state)}
      </main>
    </div>
  </div>
  {dialog_shell()}
</body>
</html>"""

    @staticmethod
    def _sidebar(state: PrototypePageState) -> str:
        links = "".join(
            f"""<li><a href="{escape(item.href)}" class="nav-link{" is-active" if item.active else ""}"
                 {'aria-current="page"' if item.active else ""}>
              <span class="nav-link__icon" aria-hidden="true">{escape(item.icon)}</span>
              <span>{escape(item.label)}</span>
            </a></li>"""
            for item in state.navigation
        )
        return f"""
        <aside class="sidebar" id="primary-navigation" aria-label="ניווט ראשי">
          <div class="brand"><span class="brand__mark" aria-hidden="true">S</span>
            <span><strong>SemesterPilot</strong><small>לומדים בקצב שלך</small></span>
          </div>
          <nav><ul>{links}</ul></nav>
          <div class="sidebar__footer">
            <div class="avatar" aria-hidden="true">ש</div>
            <span><strong>שלום, שולמית</strong><small>סמסטר 2027א</small></span>
          </div>
        </aside>"""

    @staticmethod
    def _topbar(state: PrototypePageState) -> str:
        return f"""
        <header class="topbar">
          <button class="icon-button mobile-menu" type="button" aria-label="פתיחת תפריט"
                  aria-controls="primary-navigation" aria-expanded="false" data-menu-toggle>☰</button>
          <div class="topbar__context"><span class="topbar__dot" aria-hidden="true"></span>
            <span>{escape(state.page_title)}</span></div>
          <div class="topbar__actions">
            <button class="icon-button" type="button" aria-label="חיפוש">⌕</button>
            <button class="icon-button" type="button" aria-label="התראות">♢</button>
          </div>
        </header>"""

    def _content(self, state: PrototypePageState) -> str:
        if state.page_key == "states":
            return self._states()
        if state.page_key == "import":
            return self._import_preview(state.import_preview)
        if state.page_key != "overview":
            return self._placeholder(state.page_title)
        cards = "".join(assignment_card(assignment) for assignment in state.assignments)
        return f"""
        <section class="hero-card" aria-labelledby="hero-title">
          <div><span class="hero-card__kicker">בוקר טוב</span><h2 id="hero-title">יש לך מקום להתקדם היום</h2>
            <p>שתי מטלות מחכות לך השבוע. גם צעד קטן נחשב.</p>
            <div class="hero-card__actions">{button("למטלות שלי")}{button("הצגת מצבי מערכת", variant="ghost", attributes="onclick=\"location.href='/?page=states'\"")}</div>
          </div><div class="hero-card__orb" aria-hidden="true"><span>62%</span><small>בקצב טוב</small></div>
        </section>
        <section class="section-heading"><div><p class="eyebrow">במוקד</p><h2>המטלות הקרובות</h2></div>
          <a href="/?page=assignments">לכל המטלות <span aria-hidden="true">←</span></a></section>
        <div class="card-grid">{cards}</div>
        <section class="component-showcase" aria-labelledby="form-title">
          <div><p class="eyebrow">רכיבים חוזרים</p><h2 id="form-title">טופס לדוגמה</h2></div>
          <div class="form-grid">{text_input("search-course", "חיפוש קורס", "לדוגמה: מערכות מידע")}
            {select_input("semester", "סמסטר", ("2027א", "2026ג", "2026ב"))}</div>
          <div class="showcase-row">{badge("חדש", tone="success")}{status_chip("בתהליך", tone="info")}
            {button("פתיחת חלון", variant="secondary", attributes="data-dialog-open")}</div>
        </section>"""

    @staticmethod
    def _states() -> str:
        return f"""
        <div class="state-grid">
          <div class="card state-card"><p class="eyebrow">מצב ריק</p>{empty_state("הכול נקי כאן", "כשיהיו מטלות חדשות הן יופיעו במקום הזה.")}</div>
          <div class="card state-card"><p class="eyebrow">מצב טעינה</p>{loading_state("מסדרים עבורך את הנתונים לדוגמה.")}</div>
        </div>
        <div class="state-stack">
          {alert("לא הצלחנו להשלים את הפעולה", "הנתונים נשארו ללא שינוי. אפשר לנסות שוב בעוד רגע.", tone="danger")}
          {alert("הייבוא מוכן לבדיקה", "עברו על הסיכום לפני שתבחרו להמשיך.", tone="success")}
          <div class="card dialog-example"><div><p class="eyebrow">חלון דו־שיח</p><h2>אישור ממוקד ונגיש</h2>
            <p>החלון שומר את המיקוד ונסגר גם באמצעות Escape.</p></div>
            {button("פתיחת הדוגמה", attributes="data-dialog-open")}</div>
        </div>"""

    @staticmethod
    def _import_preview(preview: ImportPreviewState) -> str:
        metrics = "".join(
            f"""<div class="metric metric--{escape(metric.tone)}">
              <span>{escape(metric.label)}</span><strong>{metric.value}</strong>
            </div>"""
            for metric in preview.metrics
        )
        safety = alert(
            "הקובץ בטוח לתצוגה",
            "זהו מסך אב־טיפוס בלבד. כפתור ההמשך אינו מפעיל סנכרון אמיתי.",
            tone="success" if preview.is_safe else "danger",
        )
        sample_course = course_identity(CourseIdentityState("10645", "תכנון וניתוח מערכות מידע", "turquoise"))
        return f"""
        <section class="import-file card" aria-labelledby="import-file-title">
          <span class="import-file__icon" aria-hidden="true">ICS</span>
          <div><p class="eyebrow">{escape(preview.source_name)}</p><h2 id="import-file-title">{escape(preview.file_name)}</h2>
            <p>{escape(preview.summary)}</p></div>{badge("נתוני הדגמה", tone="info")}
        </section>
        {safety}
        <section aria-labelledby="summary-title"><div class="section-heading"><div><p class="eyebrow">סיכום</p>
          <h2 id="summary-title">מה נמצא בקובץ?</h2></div></div><div class="metrics-grid">{metrics}</div></section>
        <section class="card preview-list" aria-labelledby="preview-title"><div class="section-heading">
          <div><p class="eyebrow">דוגמה</p><h2 id="preview-title">פריטים שזוהו</h2></div>
          {button("סנכרון אינו זמין באב־טיפוס", variant="disabled", attributes='disabled aria-disabled="true"')}</div>
          <div class="preview-row">{sample_course}{status_chip("מטלה חדשה", tone="success")}</div>
        </section>"""

    @staticmethod
    def _placeholder(title: str) -> str:
        return empty_state(
            f"{title} עדיין בבנייה", "בשלב זה מוצגת רק תשתית הניווט. הפונקציונליות תתווסף באבן דרך עתידית."
        )

    @staticmethod
    def _notice(message: str | None) -> str:
        if message is None:
            return ""
        return f'<p class="prototype-notice" role="status">{escape(message)}</p>'
