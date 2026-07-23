from html import escape

from semester_pilot.ui.components import empty_state, status_chip
from semester_pilot.ui.theme import DEFAULT_THEME_ASSETS, ThemeAssets
from semester_pilot.ui.view_models.assignment_models import AssignmentDetailState, AssignmentListState


class AssignmentView:
    """Renders assignment list and detail state without persistence knowledge."""

    def __init__(self, assets: ThemeAssets = DEFAULT_THEME_ASSETS) -> None:
        self._assets = assets

    def render_list(self, state: AssignmentListState) -> str:
        filters = (
            ("incomplete", "לא הושלמו"),
            ("completed", "הושלמו"),
            ("overdue", "באיחור"),
            ("due_today", "להגשה היום"),
            ("due_this_week", "להגשה השבוע"),
            ("missing", "חסרות במקור"),
        )
        filter_controls = "".join(
            f'<label class="filter-chip"><input type="checkbox" name="filter" value="{key}" '
            f"{'checked' if key in state.selected_filters else ''}><span>{label}</span></label>"
            for key, label in filters
        )
        course_options = '<option value="">כל הקורסים</option>' + "".join(
            f'<option value="{escape(code)}" {"selected" if code == state.selected_course else ""}>'
            f"{escape(name)} · {escape(code)}</option>"
            for code, name in state.courses
        )
        cards = "".join(self._card(item) for item in state.assignments)
        content = cards or empty_state("אין מטלות שמתאימות לחיפוש", "אפשר לשנות את החיפוש או להסיר מסנן ולנסות שוב.")
        return self._document(
            "המטלות שלי",
            f"""{self._shell_start(state.navigation, "מטלות")}
            <main id="main-content" class="main-content assignments-content" tabindex="-1">
              <header class="page-header"><div><p class="eyebrow">מרכז המטלות</p><h1>המטלות שלי</h1>
                <p>חיפוש, סינון ומעקב אחר ההתקדמות — בלי לשנות את פרטי המקור.</p></div>
                <span class="assignment-total">{len(state.assignments)} מטלות</span></header>
              <form class="assignment-filters card" method="get" action="/assignments" aria-label="חיפוש וסינון מטלות">
                <div class="filter-search"><label for="assignment-search">חיפוש</label>
                  <input id="assignment-search" type="search" name="search" value="{escape(state.search)}"
                         placeholder="כותרת, קורס או הערה אישית"></div>
                <div class="filter-select"><label for="course-filter">קורס</label><select id="course-filter" name="course">{course_options}</select></div>
                <div class="filter-select"><label for="priority-filter">עדיפות</label><select id="priority-filter" name="priority">
                  {self._options((("", "כל העדיפויות"), ("URGENT", "דחופה"), ("HIGH", "גבוהה"), ("NORMAL", "רגילה"), ("LOW", "נמוכה")), state.selected_priority)}</select></div>
                <div class="filter-select"><label for="sort-filter">מיון</label><select id="sort-filter" name="sort">
                  {self._options((("due_soon", "מועד קרוב"), ("due_latest", "מועד רחוק"), ("priority", "עדיפות"), ("course", "קורס"), ("completion", "השלמה"), ("recently_updated", "עודכנו לאחרונה")), state.selected_sort)}</select></div>
                <fieldset class="filter-chips"><legend>מצב ומועד</legend>{filter_controls}</fieldset>
                <div class="filter-actions"><a class="button button--secondary" href="/assignments">ניקוי</a>
                  <button class="button button--primary" type="submit">הצגת תוצאות</button></div>
              </form>
              <section class="assignment-list" aria-label="רשימת מטלות">{content}</section>
            </main>{self._shell_end()}""",
        )

    def render_detail(self, state: AssignmentDetailState) -> str:
        errors = dict(state.field_errors)
        global_feedback = (
            f'<div class="alert alert--danger" role="alert">{escape(state.global_error)}</div>'
            if state.global_error
            else f'<div class="alert alert--success" role="status" aria-live="polite">{escape(state.success_message)}</div>'
            if state.success_message
            else ""
        )
        missing = (
            status_chip("חסרה מלוח המקור", tone="warning")
            if state.is_missing
            else status_chip("מסונכרנת", tone="success")
        )
        return self._document(
            state.title,
            f"""<main id="main-content" class="assignment-detail-page" tabindex="-1">
              <a class="back-link" href="/assignments">→ חזרה לכל המטלות</a>
              <header class="assignment-detail-header"><div><p class="eyebrow">פרטי מטלה</p><h1>{escape(state.title)}</h1>
                <p>{escape(state.course_label)}</p></div>{missing}</header>
              {global_feedback}
              <div class="assignment-detail-grid">
                <section class="card readonly-details" aria-labelledby="imported-title"><p class="eyebrow">מידע מיובא · לקריאה בלבד</p>
                  <h2 id="imported-title">פרטי לוח השנה</h2>
                  <dl>
                  {self._readonly("כותרת מקורית", state.title)}{self._readonly("קורס", state.course_label)}
                  {self._readonly("מועד אחרון", state.due_label)}{self._readonly("סוג אירוע", state.imported_event_label)}
                  {self._readonly("זהות מקור", state.source_identity_label)}
                  {self._readonly("מיקום", state.location or "לא צוין")}
                  {self._readonly("תיאור", state.description or "אין תיאור מיובא")}
                  </dl>
                </section>
                <section class="card personal-details" aria-labelledby="personal-title"><p class="eyebrow">המרחב האישי שלי</p>
                  <h2 id="personal-title">התקדמות והערות</h2>
                  <form data-assignment-form data-assignment-id="{state.id}" novalidate>
                    <input type="hidden" name="version" value="{state.version}">
                    <div class="field"><label for="priority">עדיפות</label><select id="priority" name="priority" aria-describedby="priority-error">
                      {self._options((("LOW", "נמוכה"), ("NORMAL", "רגילה"), ("HIGH", "גבוהה"), ("URGENT", "דחופה")), state.priority)}</select>
                      {self._field_error("priority", errors)}</div>
                    <div class="field"><label for="progress">התקדמות: <output data-progress-output>{escape(state.progress_percentage)}%</output></label>
                      <input id="progress" type="range" name="progress_percentage" min="0" max="100" value="{escape(state.progress_percentage)}" data-progress-input aria-describedby="progress_percentage-error">
                      {self._field_error("progress_percentage", errors)}</div>
                    <div class="field"><label for="estimated">זמן לימוד משוער בדקות</label>
                      <input id="estimated" type="number" name="estimated_minutes" min="0" max="100000" value="{escape(state.estimated_minutes)}" aria-describedby="estimated_minutes-error">
                      {self._field_error("estimated_minutes", errors)}</div>
                    <div class="field"><label for="notes">הערות אישיות</label>
                      <textarea id="notes" name="notes" maxlength="10000" rows="7" aria-describedby="notes-help notes-error">{escape(state.notes)}</textarea>
                      <small id="notes-help">עד 10,000 תווים. המידע נשמר במחשב שלך בלבד.</small>{self._field_error("notes", errors)}</div>
                    <label class="completion-toggle"><input type="checkbox" name="is_completed" value="true" {"checked" if state.is_completed else ""}>
                      <span><strong>המטלה הושלמה</strong><small>סימון ישנה את ההתקדמות ל־100%</small></span></label>
                    {self._field_error("form", errors)}
                    <button class="button button--primary save-button" type="submit" data-save-button>שמירת שינויים</button>
                    <span class="sr-only" role="status" aria-live="polite" data-save-status></span>
                  </form>
                </section>
              </div>
              {self._subtasks(state)}
            </main>""",
        )

    @staticmethod
    def _subtasks(state: AssignmentDetailState) -> str:
        draft = dict(state.subtask_draft)
        feedback = (
            f'<div class="alert alert--danger" role="alert">{escape(state.subtask_error)}</div>'
            if state.subtask_error
            else ""
        )
        items = (
            "".join(
                f'''<li class="subtask-item" data-subtask-id="{item.id}"><form data-subtask-form data-assignment-id="{state.id}">
              <input type="hidden" name="subtask_id" value="{item.id}"><input type="hidden" name="version" value="{item.version}">
              <label><span class="sr-only">כותרת תת־משימה</span><input name="title" maxlength="200" required value="{escape(item.title)}"></label>
              <label><span class="sr-only">הערות</span><input name="notes" maxlength="10000" value="{escape(item.notes)}"></label>
              <label><span class="sr-only">זמן משוער בדקות</span><input type="number" min="1" name="estimated_minutes" value="{escape(item.estimated_minutes)}"></label>
              <button class="button button--secondary" type="submit">שמירה</button></form>
              <div class="subtask-actions" role="group" aria-label="פעולות עבור {escape(item.title)}">
                <button type="button" data-subtask-action="{"reopen" if item.completed else "complete"}" data-id="{item.id}" data-version="{item.version}">{"פתיחה מחדש" if item.completed else "השלמה"}</button>
                <button type="button" data-subtask-action="up" data-id="{item.id}" data-version="{item.version}" aria-label="הזזה למעלה">↑</button>
                <button type="button" data-subtask-action="down" data-id="{item.id}" data-version="{item.version}" aria-label="הזזה למטה">↓</button>
                <button type="button" data-subtask-delete data-id="{item.id}" data-version="{item.version}">מחיקה</button>
              </div></li>'''
                for item in state.subtasks
            )
            or '<li class="empty-state"><strong>עדיין אין תתי־משימות</strong><span>אפשר לפרק את המטלה לצעדים קטנים וברורים.</span></li>'
        )
        return f'''<section class="card subtasks-card" aria-labelledby="subtasks-title"><header><div><p class="eyebrow">צעדים אישיים</p><h2 id="subtasks-title">תתי־משימות</h2></div><strong>{state.subtask_completed}/{state.subtask_total} · {state.subtask_percentage}%</strong></header>
          <div class="progress" role="progressbar" aria-label="התקדמות בתתי־משימות" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{state.subtask_percentage}"><span style="--progress:{state.subtask_percentage}%"></span></div>
          <p>התקדמות זו נפרדת מהתקדמות המטלה. השלמת כל הצעדים אינה משלימה את המטלה אוטומטית.</p>{feedback}
          <form class="subtask-create" data-subtask-form data-assignment-id="{state.id}" novalidate><label>כותרת<input name="title" maxlength="200" required value="{escape(draft.get("title", ""))}"></label><label>הערות<input name="notes" maxlength="10000" value="{escape(draft.get("notes", ""))}"></label><label>זמן משוער בדקות<input type="number" min="1" name="estimated_minutes" value="{escape(draft.get("estimated_minutes", ""))}"></label><button class="button button--primary" type="submit">הוספת תת־משימה</button><span class="sr-only" role="status" aria-live="polite" data-subtask-status></span></form>
          <ol class="subtask-list">{items}</ol>
          <dialog data-delete-dialog aria-labelledby="delete-title"><h2 id="delete-title">למחוק את תת־המשימה?</h2><p>רק תת־המשימה שנבחרה תימחק. המטלה תישאר ללא שינוי.</p><div><button type="button" data-delete-cancel>ביטול</button><button class="button button--primary" type="button" data-delete-confirm>מחיקה</button></div></dialog>
        </section>'''

    @staticmethod
    def _card(item) -> str:
        flags = (status_chip("באיחור", tone="danger") if item.is_overdue else "") + (
            status_chip("חסרה במקור", tone="warning") if item.is_missing else ""
        )
        return f"""<article class="managed-assignment card"><div class="managed-assignment__head">
          <span class="dashboard-assignment__course" aria-hidden="true">{escape(item.course_code[:2])}</span>
          <div><small>{escape(item.course_name)} · {escape(item.course_code)}</small><h2>{escape(item.title)}</h2></div>
          <a class="button button--secondary" href="/assignments/{item.id}">פתיחת פרטים</a></div>
          <div class="managed-assignment__meta"><span>הגשה: <strong>{escape(item.due_label)}</strong></span>
            {status_chip(item.status_label, tone=item.status_tone)}{status_chip(item.priority_label, tone=item.priority_tone)}{flags}</div>
          <div class="progress-row"><span>התקדמות</span><strong>{item.progress}%</strong></div>
          <div class="progress" role="progressbar" aria-label="התקדמות במטלה" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{item.progress}"><span style="--progress: {item.progress}%"></span></div>
        </article>"""

    def _document(self, title: str, content: str) -> str:
        return f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} | SemesterPilot</title>
          <link rel="stylesheet" href="{escape(self._assets.stylesheet_url)}"><script src="{escape(self._assets.interaction_script_url)}" defer></script>
          </head><body><a class="skip-link" href="#main-content">דלגו לתוכן הראשי</a>{content}</body></html>"""

    @staticmethod
    def _shell_start(navigation, context: str) -> str:
        links = "".join(
            f'<li><a href="{escape(item.href)}" class="nav-link{" is-active" if item.active else ""}" {"aria-current=page" if item.active else ""}><span class="nav-link__icon" aria-hidden="true">{escape(item.icon)}</span><span>{escape(item.label)}</span></a></li>'
            for item in navigation
        )
        return f'<div class="app-shell"><aside class="sidebar" id="primary-navigation" aria-label="ניווט ראשי"><div class="brand"><span class="brand__mark">S</span><span><strong>SemesterPilot</strong><small>לומדים בקצב שלך</small></span></div><nav><ul>{links}</ul></nav></aside><div class="app-frame"><header class="topbar"><button class="icon-button mobile-menu" type="button" aria-label="פתיחת תפריט" aria-controls="primary-navigation" aria-expanded="false" data-menu-toggle>☰</button><div class="topbar__context"><span class="topbar__dot"></span><span>{escape(context)}</span></div></header>'

    @staticmethod
    def _shell_end() -> str:
        return "</div></div>"

    @staticmethod
    def _options(options: tuple[tuple[str, str], ...], selected: str) -> str:
        return "".join(
            f'<option value="{escape(value)}" {"selected" if value == selected else ""}>{escape(label)}</option>'
            for value, label in options
        )

    @staticmethod
    def _readonly(label: str, value: str) -> str:
        return f'<div class="readonly-row"><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>'

    @staticmethod
    def _field_error(field: str, errors: dict[str, str]) -> str:
        message = errors.get(field)
        return (
            f'<small class="field-error" id="{field}-error" role="alert">{escape(message)}</small>'
            if message
            else f'<small id="{field}-error"></small>'
        )
