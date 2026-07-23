from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemeAssets:
    stylesheet_url: str
    interaction_script_url: str


DEFAULT_THEME_ASSETS = ThemeAssets(
    stylesheet_url="/static/prototype.css",
    interaction_script_url="/static/prototype.js",
)
