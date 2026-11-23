const COMPONENTS = ["header", "sidebar", "footer"];

export async function loadComponents() {
  const results = await Promise.all(
    COMPONENTS.map(async (name) => {
      const container = document.querySelector(`[data-component="${name}"]`);
      if (!container) {
        throw new Error(`Missing container for the "${name}" component.`);
      }

<<<<<<< HEAD
      const response = await fetch(`components/${name}.html`);
=======
      const response = await fetch(new URL(`../components/${name}.html`, import.meta.url));
>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
      if (!response.ok) {
        throw new Error(`Unable to load "${name}" component: ${response.status} ${response.statusText}`);
      }

      container.innerHTML = await response.text();
      return name;
    }),
  );

  return results;
}
