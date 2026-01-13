import frappeUIPreset from "frappe-ui/tailwind"

export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			colors: {
				primary: "hsl(var(--bg-primary) / <alpha-value>)",
				secondary: "hsl(var(--bg-secondary) / <alpha-value>)",
				tertiary: "hsl(var(--bg-tertiary) / <alpha-value>)",
				accent: {
					purple: "hsl(var(--accent-primary) / <alpha-value>)",
					cyan: "hsl(var(--accent-secondary) / <alpha-value>)",
					danger: "hsl(var(--accent-error) / <alpha-value>)",
				}
			},
			fontFamily: {
				sans: ['Inter', 'ui-sans-serif', 'system-ui'],
			}
		},
	},
	plugins: [],
}
