# Depends(get_session) Audit Progress

## Prerequisite (done)
- [x] `persist()` standalone (no args) — config.py
- [x] `persist(db)` → `persist()` in configs.py, tasks.py, openai.py, auths.py
- [x] Bug fix: chats.py:409 `db=db` on method that doesn't accept it
- [x] Remove `db: Session = Depends(get_session)` from configs.py (4 endpoints)
- [x] Remove `db: Session = Depends(get_session)` from tasks.py (1 endpoint)
- [x] Remove `db: Session = Depends(get_session)` from openai.py (1 endpoint)
- [x] Clean imports: configs.py, tasks.py, openai.py

## users.py (11 endpoints)
- [x] :57 get_users — DROP (single read)
- [x] :78 get_all_users — DROP (single read)
- [x] :90 search_users — DROP (single read)
- [x] :115 get_user_settings_by_session_user — DROP (single read)
- [x] :137 update_user_settings_by_session_user — DROP (single self-contained write)
- [x] :157 get_user_info_by_session_user — DROP (single read)
- [x] :176 update_user_info_by_session_user — DROP (detached pydantic model, no shared txn benefit)
- [x] :207 get_user_by_id — DROP (two independent reads, no writes)
- [x] :234 get_user_info_by_id — DROP (single read)
- [x] :294 update_user_by_id — KEEP (email uniqueness-gate: get_user_by_email check gates 3 subsequent writes)
- [x] :375 delete_user_by_id — DROP (guard read + single independent write)

## chats.py (25 endpoints)
- [x] :43 get_session_user_chat_list — DROP (single read)
- [x] :75 delete_all_user_chats — DROP (single write, own session)
- [x] :95 get_user_chat_list_by_user_id — DROP (single read)
- [x] :125 create_new_chat — DROP (single write, own session)
- [x] :146 import_chats — DROP (single write, own session)
- [x] :168 search_user_chats — DROP (read + best-effort tag cleanup, no atomicity needed)
- [x] :202 get_chats_by_folder_id — DROP (two independent reads)
- [x] :224 get_chat_list_by_folder_id — DROP (single read)
- [x] :251 get_user_pinned_chats — DROP (single read)
- [x] :263 get_user_chats — DROP (single read)
- [x] :276 get_all_user_tags — DROP (single read, agents drifted due to line shifts but covered all 4)
- [x] :295 get_all_user_chats_in_db — DROP (single read)
- [x] :318 get_user_chat_list_by_tag_name — DROP (read + idempotent tag cleanup)
- [x] :336 get_chat_by_id — DROP (single read)
- [x] :393 update_chat_message_by_id — DROP (read guard only, write already standalone)
- [x] :455 send_chat_message_event_by_id — DROP (read guard, no writes)
- [x] :498 delete_chat_by_id — DROP (sequential standalone ops, benign race outcomes)
- [x] :536 get_pinned_status_by_id — DROP (single read)
- [x] :554 pin_chat_by_id — DROP (auth guard + single write, concurrent delete = graceful None)
- [x] :580 clone_chat_by_id — DROP (read source + write new row with fresh UUID, independent)
- [x] :634 update_chat_folder_id_by_id — DROP (auth guard + single write, concurrent delete = None)
- [x] :655 get_chat_tags_by_id — DROP (two independent reads)
- [x] :677 add_tag_by_id_and_tag_name — DROP (write is self-contained with own duplicate guard)
- [x] :714 delete_tag_by_id_and_tag_name — DROP (5 independent ops, orphan delete idempotent)
- [x] :744 delete_all_tags_by_id — DROP (sequential ops, no cross-call invariant)

## files.py (9 endpoints)
- [x] :53 upload_file — DROP (single write, own session)
- [x] :141 list_files — DROP (single read per branch)
- [x] :165 search_files — DROP (single read)
- [x] :193 delete_all_files — DROP (single write, own session)
- [x] :221 get_file_by_id — DROP (single read)
- [x] :250 get_file_content_by_id — DROP (single read)
- [x] :312 get_html_file_content_by_id — DROP (two independent reads)
- [x] :359 get_file_content_by_id_and_name — DROP (single read)
- [x] :398 delete_file_by_id — DROP (read guard + single write, detached model)

## auths.py (9 endpoints)
- [x] :132 get_session_user — DROP (db declared but never used)
- [x] :189 update_profile — DROP (single write, own session)
- [x] :218 update_timezone — DROP (single write, own session)
- [x] :240 update_password — DROP (auth guard read + single write on immutable user ID)
- [x] :272 signin — KEEP (WEBUI_AUTH=False path: has_users + insert_new_auth first-signup race)
- [x] :366 signup — KEEP (has_users + get_user_by_email + insert_new_auth: dual admin + email dup races)
- [x] :441 add_user — KEEP (email uniqueness-gate-insert, no unique constraint on email column)
- [x] :496 get_admin_details — DROP (two independent reads)
- [x] :557 update_admin_config — DROP (db unused, persist() standalone)

## models.py (12 endpoints)
- [x] :61 get_models — DROP (single read)
- [x] :96 get_base_models — DROP (single read)
- [x] :108 get_model_tags — DROP (single read)
- [x] :134 create_new_model — DROP (id is PK+unique, DB catches duplicates)
- [x] :175 export_models — DROP (single read)
- [x] :200 import_models — KEEP (batch read gates update-vs-insert loop, all-or-nothing batch)
- [x] :268 sync_models — DROP (single self-contained call)
- [x] :285 get_model_by_id — DROP (single read)
- [x] :346 toggle_model_by_id — DROP (guard read + single write, write re-reads internally)
- [x] :380 update_model_by_id — DROP (guard + single independent write)
- [x] :410 delete_model_by_id — DROP (guard + single write, double-delete harmless)
- [x] :431 delete_all_models — DROP (single write)

## folders.py (7 endpoints)
- [x] :38 get_folders — DROP (independent per-folder cleanup, idempotent)
- [x] :84 create_folder — DROP (no unique constraint, shared session doesn't help TOCTOU)
- [x] :115 get_folder_by_id — DROP (single read)
- [x] :137 update_folder_name_by_id — DROP (no unique constraint, DEFERRED lock at flush after reads)
- [x] :186 update_folder_parent_id_by_id — DROP (no unique constraint, DEFERRED lock after reads)
- [x] :233 update_folder_is_expanded_by_id — DROP (guard + single self-contained write)
- [x] :266 delete_folder_by_id — KEEP (cascading multi-table delete needs all-or-nothing rollback)

## Post-audit
- [x] Clean up unused imports per file (Session, get_session) — chats.py, files.py fully cleaned; users/auths/models/folders still need them for KEEP endpoints
- [x] `uv run black . --check --exclude ".venv/|/venv/"` — reformatted 6 files
- [x] `uv run pytest` — 24/24 passed

## Summary
- 73 endpoints audited (75 original - 2 already done: configs.py persist-only)
- 67 DROP, 6 KEEP
- KEEP: users.py update_user_by_id, auths.py signin/signup/add_user, models.py import_models, folders.py delete_folder_by_id
