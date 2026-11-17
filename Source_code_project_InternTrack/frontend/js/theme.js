const THEME_STORAGE_KEY = "intertrack-theme";
const LIGHT_THEME = "light";
const DARK_THEME = "dark";

function readThemePreference() {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY) === DARK_THEME
      ? DARK_THEME
      : LIGHT_THEME;
  } catch (error) {
    console.error("Could not read the saved color theme.", error);
    return LIGHT_THEME;
  }
}

function updateThemeButtons(theme) {
  const isDark = theme === DARK_THEME;
  const label = isDark
    ? "Chuyển sang giao diện sáng"
    : "Chuyển sang giao diện tối";

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", String(isDark));
    button.title = label;
  });
}

function applyTheme(theme, persist = false) {
  document.documentElement.dataset.theme = theme;
  updateThemeButtons(theme);

  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) {
    themeColor.content = theme === DARK_THEME ? "#101a2b" : "#f5f7fb";
  }

  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch (error) {
      console.error("Could not save the selected color theme.", error);
    }
  }
}

applyTheme(readThemePreference());

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }

  const toggle = event.target.closest("[data-theme-toggle]");
  if (!(toggle instanceof HTMLButtonElement)) {
    return;
  }

  const currentTheme = document.documentElement.dataset.theme;
  applyTheme(currentTheme === DARK_THEME ? LIGHT_THEME : DARK_THEME, true);
});

const themeButtonObserver = new MutationObserver(() => {
  updateThemeButtons(document.documentElement.dataset.theme || LIGHT_THEME);
});
themeButtonObserver.observe(document.documentElement, {
  childList: true,
  subtree: true,
});
