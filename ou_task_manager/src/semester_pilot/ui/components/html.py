from html import escape

from semester_pilot.ui.view_models.models import AssignmentState, CourseIdentityState


def button(label: str, *, variant: str = "primary", button_type: str = "button", attributes: str = "") -> str:
    return (
        f'<button class="button button--{escape(variant)}" type="{escape(button_type)}" {attributes}>'
        f"{escape(label)}</button>"
    )


def badge(label: str, *, tone: str = "neutral") -> str:
    return f'<span class="badge badge--{escape(tone)}">{escape(label)}</span>'


def status_chip(label: str, *, tone: str = "neutral") -> str:
    return (
        f'<span class="status-chip status-chip--{escape(tone)}"><span aria-hidden="true"></span>{escape(label)}</span>'
    )


def text_input(input_id: str, label: str, placeholder: str, *, value: str = "") -> str:
    return f"""
    <div class="field">
      <label for="{escape(input_id)}">{escape(label)}</label>
      <input id="{escape(input_id)}" name="{escape(input_id)}" type="text"
             value="{escape(value)}" placeholder="{escape(placeholder)}">
    </div>"""


def select_input(input_id: str, label: str, options: tuple[str, ...]) -> str:
    rendered_options = "".join(f'<option value="{escape(option)}">{escape(option)}</option>' for option in options)
    return f"""
    <div class="field">
      <label for="{escape(input_id)}">{escape(label)}</label>
      <select id="{escape(input_id)}" name="{escape(input_id)}">{rendered_options}</select>
    </div>"""


def alert(title: str, message: str, *, tone: str = "info") -> str:
    return f"""
    <section class="alert alert--{escape(tone)}" role="alert" aria-labelledby="alert-title">
      <span class="alert__icon" aria-hidden="true">!</span>
      <div><h3 id="alert-title">{escape(title)}</h3><p>{escape(message)}</p></div>
    </section>"""


def empty_state(title: str, message: str) -> str:
    return f"""
    <section class="empty-state" aria-labelledby="empty-title">
      <span class="empty-state__art" aria-hidden="true">✓</span>
      <h3 id="empty-title">{escape(title)}</h3>
      <p>{escape(message)}</p>
      {button("לייבוא לוח שנה", variant="secondary")}
    </section>"""


def loading_state(message: str) -> str:
    return f"""
    <div class="loading-state" role="status" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span>
      <div><strong>רק רגע</strong><p>{escape(message)}</p></div>
      <span class="sr-only">התוכן בטעינה</span>
    </div>"""


def page_header(eyebrow: str, title: str, description: str) -> str:
    return f"""
    <header class="page-header">
      <div><p class="eyebrow">{escape(eyebrow)}</p><h1>{escape(title)}</h1><p>{escape(description)}</p></div>
      <div class="page-header__actions">{button("פעולה לדוגמה", variant="secondary")}</div>
    </header>"""


def course_identity(course: CourseIdentityState) -> str:
    initials = "".join(word[0] for word in course.name.split()[:2])
    return f"""
    <div class="course-identity">
      <span class="course-identity__mark course-identity__mark--{escape(course.color)}" aria-hidden="true">
        {escape(initials)}
      </span>
      <span><strong>{escape(course.name)}</strong><small>קורס {escape(course.code)}</small></span>
    </div>"""


def assignment_card(assignment: AssignmentState) -> str:
    return f"""
    <article class="card assignment-card">
      <div class="assignment-card__top">
        {course_identity(assignment.course)}
        {status_chip(assignment.status_label, tone=assignment.status_tone)}
      </div>
      <h3>{escape(assignment.title)}</h3>
      <p class="assignment-card__due"><span aria-hidden="true">◷</span> הגשה: {escape(assignment.due_label)}</p>
      <div class="progress-row">
        <span>התקדמות</span><strong>{assignment.progress}%</strong>
      </div>
      <div class="progress" role="progressbar" aria-label="התקדמות במטלה" aria-valuemin="0"
           aria-valuemax="100" aria-valuenow="{assignment.progress}">
        <span style="--progress: {assignment.progress}%"></span>
      </div>
    </article>"""


def dialog_shell() -> str:
    return f"""
    <dialog class="dialog" aria-labelledby="dialog-title" aria-describedby="dialog-description" data-dialog>
      <form method="dialog"><button class="dialog__close icon-button" aria-label="סגירת חלון">×</button></form>
      <div class="dialog__icon" aria-hidden="true">✓</div>
      <h2 id="dialog-title">לשמור את הבחירה?</h2>
      <p id="dialog-description">זו הדגמת ממשק בלבד. שום מידע אמיתי לא ישתנה.</p>
      <div class="dialog__actions"><form method="dialog">{button("ביטול", variant="secondary", button_type="submit")}</form>
        <form method="dialog">{button("אישור", button_type="submit")}</form></div>
    </dialog>"""
