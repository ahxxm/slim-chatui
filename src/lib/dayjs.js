import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(duration);
dayjs.extend(relativeTime);

const dayjsLocaleLoaders = import.meta.glob('../../node_modules/dayjs/locale/*.js');
const loadedDayjsLocales = new Set(['en']);

/** @type {Record<string, string[]>} */
const dayjsLocaleAliases = {
	'ie-ga': ['ga']
};

/**
 * @param {string | null | undefined} locale
 * @returns {string[]}
 */
const getDayjsLocaleCandidates = (locale) => {
	if (!locale) {
		return [];
	}

	const normalizedLocale = locale.toLowerCase().replaceAll('_', '-');
	const localeSegments = normalizedLocale.split('-').filter(Boolean);
	const localeCandidates = new Set(dayjsLocaleAliases[normalizedLocale] ?? []);

	localeCandidates.add(normalizedLocale);

	if (localeSegments.length >= 2) {
		localeCandidates.add(`${localeSegments[0]}-${localeSegments[1]}`);
	}

	localeCandidates.add(localeSegments[0]);

	return [...localeCandidates].filter(Boolean);
};

/**
 * @param {string | string[] | null | undefined} locales
 */
export const setDayjsLocale = async (locales) => {
	const requestedLocales = Array.isArray(locales) ? locales : [locales];

	for (const locale of requestedLocales) {
		for (const candidate of getDayjsLocaleCandidates(locale)) {
			if (loadedDayjsLocales.has(candidate)) {
				dayjs.locale(candidate);
				return candidate;
			}

			const loadLocale = dayjsLocaleLoaders[`../../node_modules/dayjs/locale/${candidate}.js`];
			if (!loadLocale) {
				continue;
			}

			await loadLocale();
			loadedDayjsLocales.add(candidate);
			dayjs.locale(candidate);
			return candidate;
		}
	}

	dayjs.locale('en');
	return 'en';
};

export default dayjs;
