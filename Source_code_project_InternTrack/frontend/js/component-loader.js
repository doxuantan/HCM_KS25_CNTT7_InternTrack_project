const COMPONENTS = ["header", "sidebar", "footer"];

export async function loadComponents() {
  const results = await Promise.all(
    COMPONENTS.map(async (name) => {
      const container = document.querySelector(`[data-component="${name}"]`);
      if (!container) {
        throw new Error(`Missing container for the "${name}" component.`);
      }

      const response = await fetch(new URL(`../components/${name}.html`, import.meta.url));
      if (!response.ok) {
        throw new Error(`Unable to load "${name}" component: ${response.status} ${response.statusText}`);
      }

      container.innerHTML = await response.text();
      return name;
    }),
  );

  return results;
}
