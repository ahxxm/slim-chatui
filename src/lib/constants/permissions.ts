export const DEFAULT_PERMISSIONS = {
	workspace: {
		models: false,
		prompts: false,
		models_import: false,
		models_export: false,
		prompts_import: false,
		prompts_export: false
	},
	sharing: {
		models: false,
		public_models: false,
		prompts: false,
		public_prompts: false
	},
	chat: {
		controls: true,
		system_prompt: true,
		params: true,
		file_upload: true,
		web_upload: true,
		delete: true,
		delete_message: true,
		continue_response: true,
		regenerate_response: true,
		rate_response: true,
		edit: true,
		share: true,
		export: true,
		multiple_models: true,
		temporary: true,
		temporary_enforced: false
	},
	features: {
		api_keys: false,
		folders: true
	},
	settings: {
		interface: true
	}
} as const;
