from html import escape

from semester_pilot.ui.components import empty_state, status_chip
from semester_pilot.ui.theme import DEFAULT_THEME_ASSETS, ThemeAssets
from semester_pilot.ui.view_models.dashboard_models import DashboardState


class DashboardView:
    """Renders the read-only dashboard from prepared presentation state."""

    def __init__(self, assets: ThemeAssets = DEFAULT_THEME_ASSETS) -> None:
        self._assets = assets

    def render(self, state: DashboardState) -> str:
        return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#109b98">
  <title>הסקירה שלי | SemesterPilot</title>
  <link rel="stylesheet" href="{escape(self._assets.stylesheet_url)}">
  <script src="{escape(self._assets.interaction_script_url)}" defer></script>
</head>
<body>
  <a class="skip-link" href="#main-content">דלגו לתוכן הראשי</a>
  <div class="app-shell">
    {self._sidebar(state)}
    <div class="app-frame">
      {self._topbar()}
      <main id="main-content" class="main-content dashboard-content" tabindex="-1">
        {self._welcome(state)}
        <div class="dashboard-primary-grid">
          {self._agenda(state)}
          {self._assignments(state)}
        </div>
        {self._weekly(state)}
        <div class="dashboard-secondary-grid">
          {self._progress(state)}
          {self._recent_import(state)}
        </div>
      </main>
    </div>
  </div>
</body>
</html>"""

    @staticmethod
    def _sidebar(state: DashboardState) -> str:
        links = "".join(
            f"""<li><a href="{escape(item.href)}" class="nav-link{" is-active" if item.active else ""}"
                 {'aria-current="page"' if item.active else ""}>
              <span class="nav-link__icon" aria-hidden="true">{escape(item.icon)}</span>
              <span>{escape(item.label)}</span></a></li>"""
            for item in state.navigation
        )
        return f"""
        <aside class="sidebar" id="primary-navigation" aria-label="ניווט ראשי">
          <div class="brand"><span class="brand__mark" aria-hidden="true">S</span>
            <span><strong>SemesterPilot</strong><small>לומדים בקצב שלך</small></span></div>
          <nav><ul>{links}</ul></nav>
          <div class="sidebar__footer"><div class="avatar" aria-hidden="true">ש</div>
            <span><strong>המרחב שלי</strong><small>{escape(state.semester_label)}</small></span></div>
        </aside>"""

    @staticmethod
    def _topbar() -> str:
        return """
        <header class="topbar">
          <button class="icon-button mobile-menu" type="button" aria-label="פתיחת תפריט"
                  aria-controls="primary-navigation" aria-expanded="false" data-menu-toggle>☰</button>
          <div class="topbar__context"><span class="topbar__dot" aria-hidden="true"></span><span>סקירה</span></div>
          <div class="topbar__actions"><button class="icon-button" type="button" aria-label="חיפוש" disabled>⌕</button>
            <button class="icon-button" type="button" aria-label="התראות" disabled>♢</button></div>
        </header>"""

    @staticmethod
    def _welcome(state: DashboardState) -> str:
        return f"""
        <header class="dashboard-welcome">
          <div><p class="eyebrow">{escape(state.date_label)}</p><h1>{escape(state.greeting)}</h1>
            <p>הנה תמונת המצב האקדמית שלך, בקצב נעים וברור.</p></div>
          <div class="semester-summary"><span class="semester-summary__icon" aria-hidden="true">✦</span>
            <span><small>סמסטר נוכחי</small><strong>{escape(state.semester_label)}</strong></span>
            <span class="semester-summary__divider" aria-hidden="true"></span>
            <span><small>קורסים פעילים</small><strong>{state.active_course_count}</strong></span></div>
        </header>"""

    @staticmethod
    def _agenda(state: DashboardState) -> str:
        if not state.agenda:
            content = empty_state("היום שלך פנוי", "אין שיעורים, בחינות או הגשות להיום. זמן טוב להתקדם בנחת.")
        else:
            content = (
                '<div class="agenda-list">'
                + "".join(
                    f"""<article class="agenda-item"><span class="agenda-item__time">{escape(item.time_label)}</span>
                  <span class="agenda-item__icon agenda-item__icon--{escape(item.tone)}" aria-hidden="true">{escape(item.icon)}</span>
                  <span class="agenda-item__main"><strong>{escape(item.title)}</strong>
                    <small>{escape(item.course_name or item.type_label)}</small></span>
                  {status_chip(item.type_label, tone=item.tone)}</article>"""
                    for item in state.agenda
                )
                + "</div>"
            )
        return f"""<section class="dashboard-section card" aria-labelledby="agenda-title">
          <div class="dashboard-section__heading"><div><p class="eyebrow">היום</p><h2 id="agenda-title">סדר היום</h2></div>
            <span class="section-count">{len(state.agenda)}</span></div>{content}</section>"""

    @staticmethod
    def _assignments(state: DashboardState) -> str:
        if not state.assignments:
            content = empty_state("אין מטלות קרובות", "כל הכבוד — אין כרגע מטלות פתוחות שממתינות להגשה.")
        else:
            content = (
                '<div class="dashboard-assignment-list">'
                + "".join(
                    f"""<article class="dashboard-assignment">
                  <span class="dashboard-assignment__course" aria-hidden="true">{escape(item.course_code[:2])}</span>
                  <span class="dashboard-assignment__main"><small>{escape(item.course_name)}</small>
                    <strong>{escape(item.title)}</strong><span>הגשה: {escape(item.due_label)}</span></span>
                  <span class="dashboard-assignment__meta">{status_chip(item.priority_label, tone=item.priority_tone)}
                    {status_chip(item.status_label, tone=item.status_tone)}</span></article>"""
                    for item in state.assignments
                )
                + "</div>"
            )
        return f"""<section class="dashboard-section card" aria-labelledby="assignments-title">
          <div class="dashboard-section__heading"><div><p class="eyebrow">בקרוב</p><h2 id="assignments-title">מטלות קרובות</h2></div>
            <a class="placeholder-link" href="/assignments">הצגת הכול ←</a></div>{content}</section>"""

    @staticmethod
    def _weekly(state: DashboardState) -> str:
        cards = "".join(
            f"""<article class="week-stat week-stat--{escape(item.tone)}">
              <span class="week-stat__icon" aria-hidden="true">{escape(item.icon)}</span>
              <span><strong>{item.value}</strong><small>{escape(item.label)}</small></span></article>"""
            for item in state.weekly
        )
        return f"""<section class="weekly-section" aria-labelledby="weekly-title">
          <div class="dashboard-section__heading"><div><p class="eyebrow">השבוע שלך</p><h2 id="weekly-title">מבט שבועי</h2></div></div>
          <div class="weekly-grid">{cards}</div></section>"""

    @staticmethod
    def _progress(state: DashboardState) -> str:
        counts = "".join(
            f"""<div class="progress-count"><span class="progress-count__dot progress-count__dot--{escape(item.tone)}"></span>
              <span><strong>{item.value}</strong><small>{escape(item.label)}</small></span></div>"""
            for item in state.progress
        )
        return f"""<section class="dashboard-section card progress-summary" aria-labelledby="progress-title">
          <div><p class="eyebrow">התקדמות</p><h2 id="progress-title">מצב המטלות</h2>
            <p>כל צעד קטן מקדם אותך לסיום הסמסטר.</p><div class="progress-counts">{counts}</div></div>
          <div class="progress-ring" style="--progress: {state.completion_percent}%" role="progressbar"
               aria-label="אחוז המטלות שהושלמו" aria-valuemin="0" aria-valuemax="100"
               aria-valuenow="{state.completion_percent}"><span><strong>{state.completion_percent}%</strong><small>הושלמו</small></span></div>
        </section>"""

    @staticmethod
    def _recent_import(state: DashboardState) -> str:
        recent = state.recent_import
        if recent is None:
            content = empty_state("עדיין אין ייבוא", "לאחר ייבוא לוח שנה יופיע כאן סיכום הסנכרון האחרון.")
        else:
            content = f"""<div class="recent-import"><span class="recent-import__mark" aria-hidden="true">ICS</span>
              <div><small>מקור</small><strong>{escape(recent.source_label)}</strong>
                <p>{escape(recent.summary)}</p><time>{escape(recent.synchronized_label)}</time></div></div>"""
        return f"""<section class="dashboard-section card" aria-labelledby="recent-title">
          <div class="dashboard-section__heading"><div><p class="eyebrow">עדכון אחרון</p><h2 id="recent-title">ייבוא אחרון</h2></div></div>
          {content}</section>"""
