import { WEBUI_BASE_URL } from '$lib/constants';

export const getModels = async (
	token: string = '',
	base: boolean = false,
	refresh: boolean = false
) => {
	const searchParams = new URLSearchParams();
	if (refresh) {
		searchParams.append('refresh', 'true');
	}

	let error = null;
	const res = await fetch(
		`${WEBUI_BASE_URL}/api/models${base ? '/base' : ''}?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				...(token && { authorization: `Bearer ${token}` })
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	let models = res?.data ?? [];

	return models;
};

export const stopTask = async (token: string, id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/tasks/stop/${id}`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			if ('detail' in err) {
				error = err.detail;
			} else {
				error = err;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getTaskIdsByChatId = async (token: string, chat_id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/tasks/chat/${chat_id}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			if ('detail' in err) {
				error = err.detail;
			} else {
				error = err;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getTaskConfig = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/config`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateTaskConfig = async (token: string, config: object) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/config/update`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify(config)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			if ('detail' in err) {
				error = err.detail;
			} else {
				error = err;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const generateTitle = async (
	token: string,
	model: string,
	messages: object[],
	chat_id?: string
): Promise<string | null> => {
	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/title/completions`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({ model, messages, ...(chat_id && { chat_id }) })
	});

	if (!res.ok) {
		const err = await res.json().catch(() => ({}));
		throw err.detail || 'Failed to generate title';
	}

	const data = await res.json();
	return data.title || null;
};

export const getBackendConfig = async () => {
	const res = await fetch(`${WEBUI_BASE_URL}/api/config`, {
		method: 'GET',
		credentials: 'include',
		headers: { 'Content-Type': 'application/json' }
	});

	if (!res.ok) {
		const err = await res.json().catch(() => ({}));
		throw err.detail || 'Failed to fetch backend config';
	}

	return res.json();
};

export const getVersion = async (token: string) => {
	const res = await fetch(`${WEBUI_BASE_URL}/api/version`, {
		method: 'GET',
		headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
	});

	if (!res.ok) {
		const err = await res.json().catch(() => ({}));
		throw err.detail || 'Failed to fetch version';
	}

	return res.json();
};

export interface ModelConfig {
	id: string;
	name: string;
	meta: ModelMeta;
	base_model_id?: string;
	params: ModelParams;
}

interface ModelMeta {
	description?: string;
	capabilities?: object;
	hidden?: boolean;
	user?: Record<string, any>;
	suggestion_prompts?: { content: string }[];
	tags?: { name: string }[];
}

interface ModelParams {}
