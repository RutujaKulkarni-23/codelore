import { useState, useEffect } from "react";

export function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try {
      return (localStorage.getItem("codelore_theme") as "dark" | "light") || "dark";
    } catch {
      return "dark";
    }
  });

  useEffect(() => {
    try {
      if (theme === "light") {
        document.documentElement.classList.add("theme-light");
      } else {
        document.documentElement.classList.remove("theme-light");
      }
      localStorage.setItem("codelore_theme", theme);
    } catch {
      // Graceful fallback if storage fails
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  return { theme, toggleTheme };
}
