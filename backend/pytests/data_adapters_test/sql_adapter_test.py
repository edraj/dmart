# import pytest
# from sqlmodel import create_engine, SQLModel, Session
# from data_adapters.sql_adapter import SQLAdapter
# from models.api import Query
# from models.core import Meta
# from models.enums import QueryType, ResourceType
# from datetime import datetime
#
#
# # Fixture for setting up an SQLite database for testing
# @pytest.fixture(scope="function")
# def adapter_with_db():
# 	# Use SQLite in-memory database for testing
# 	engine = create_engine("sqlite:///:memory:")
# 	SQLModel.metadata.create_all(engine)
# 	adapter = SQLAdapter()
#
# 	# Override the get_session method to use our in-memory database
# 	def get_session_override():
# 		return Session(engine)
#
# 	adapter.get_session = get_session_override
# 	return adapter
#
#
# # Test if the SQLAdapter session management works
# def test_session_management(adapter_with_db):
# 	session = adapter_with_db.get_session()
# 	assert session is not None
#
#
# # Test the save and load functionality
# @pytest.mark.asyncio
# async def test_save_and_load(adapter_with_db):
# 	meta = Meta(shortname="test_meta")
# 	await adapter_with_db.save("test_space", "/test_path", meta)
#
# 	loaded_meta = await adapter_with_db.load("test_space", "/test_path", "test_meta", Meta)
# 	assert loaded_meta.shortname == "test_meta"
#
#
# # Test query function
# @pytest.mark.asyncio
# async def test_query(adapter_with_db):
# 	query = Query(space_name="test_space", type=QueryType.spaces)
# 	total, records = await adapter_with_db.query(query)
# 	assert total == 0  # No records should exist in a fresh DB
#
#
# # Test save_payload functionality
# @pytest.mark.asyncio
# async def test_save_payload(adapter_with_db):
# 	meta = Meta(shortname="test_payload_meta")
# 	await adapter_with_db.save_payload("test_space", "/test_path", meta, None)  # You can add a real attachment
# 	assert True  # Just ensuring that the method runs without errors
#
#
# # Test handling non-existent entries
# @pytest.mark.asyncio
# async def test_load_or_none(adapter_with_db):
# 	meta = await adapter_with_db.load_or_none("test_space", "/test_path", "non_existent", Meta)
# 	assert meta is None
#
#
# # Test if load returns None for non-existent entry
# @pytest.mark.asyncio
# async def test_load_non_existent(adapter_with_db):
# 	with pytest.raises(Exception):  # Should raise exception if the object is not found
# 		await adapter_with_db.load("test_space", "/non_existent", "non_existent", Meta)
#
#
# # Test create method
# @pytest.mark.asyncio
# async def test_create(adapter_with_db):
# 	meta = Meta(shortname="new_meta")
# 	await adapter_with_db.create("test_space", "/test_path", meta)
#
# 	# Now try to load it
# 	loaded_meta = await adapter_with_db.load("test_space", "/test_path", "new_meta", Meta)
# 	assert loaded_meta.shortname == "new_meta"
#
#
# # Test the update method
# @pytest.mark.asyncio
# async def test_update(adapter_with_db):
# 	meta = Meta(shortname="updatable_meta")
# 	await adapter_with_db.create("test_space", "/test_path", meta)
#
# 	# Update the meta
# 	meta.shortname = "updated_meta"
# 	old_version = {"shortname": "updatable_meta"}
# 	new_version = {"shortname": "updated_meta"}
# 	updated_attributes = ["shortname"]
#
# 	await adapter_with_db.update("test_space", "/test_path", meta, old_version, new_version, updated_attributes, "user")
#
# 	# Now load and check the update
# 	loaded_meta = await adapter_with_db.load("test_space", "/test_path", "updated_meta", Meta)
# 	assert loaded_meta.shortname == "updated_meta"
#
#
# # Test delete method
# @pytest.mark.asyncio
# async def test_delete(adapter_with_db):
# 	meta = Meta(shortname="deletable_meta")
# 	await adapter_with_db.create("test_space", "/test_path", meta)
#
# 	await adapter_with_db.delete("test_space", "/test_path", meta, "user")
#
# 	# Now check that the entry was deleted
# 	meta = await adapter_with_db.load_or_none("test_space", "/test_path", "deletable_meta", Meta)
# 	assert meta is None
#
#
# # Test the move method
# @pytest.mark.asyncio
# async def test_move(adapter_with_db):
# 	meta = Meta(shortname="movable_meta")
# 	await adapter_with_db.create("test_space", "/src_path", meta)
#
# 	await adapter_with_db.move("test_space", "/src_path", "movable_meta", "/dest_path", "moved_meta", meta)
#
# 	# Check the moved entry
# 	moved_meta = await adapter_with_db.load("test_space", "/dest_path", "moved_meta", Meta)
# 	assert moved_meta.shortname == "moved_meta"
#
#
# # Test exception handling during update of non-existent entry
# @pytest.mark.asyncio
# async def test_update_non_existent(adapter_with_db):
# 	meta = Meta(shortname="non_existent_meta")
# 	old_version = {}
# 	new_version = {}
# 	updated_attributes = []
#
# 	with pytest.raises(Exception):
# 		await adapter_with_db.update("test_space", "/non_existent", meta, old_version, new_version, updated_attributes,
# 									 "user")
#
#
# # Test the set_sql_active_session method
# @pytest.mark.asyncio
# async def test_set_sql_active_session(adapter_with_db):
# 	result = await adapter_with_db.set_sql_active_session("test_user", "test_token")
# 	assert result is True
#
#
# # Test the set_sql_user_session method
# @pytest.mark.asyncio
# async def test_set_sql_user_session(adapter_with_db):
# 	result = await adapter_with_db.set_sql_user_session("test_user", "test_token")
# 	assert result is True
#
#
# # Test the get_sql_active_session method
# @pytest.mark.asyncio
# async def test_get_sql_active_session(adapter_with_db):
# 	await adapter_with_db.set_sql_active_session("test_user", "test_token")
# 	token = await adapter_with_db.get_sql_active_session("test_user")
# 	assert token is not None
#
#
# # Test the get_sql_user_session method
# @pytest.mark.asyncio
# async def test_get_sql_user_session(adapter_with_db):
# 	await adapter_with_db.set_sql_user_session("test_user", "test_token")
# 	token = await adapter_with_db.get_sql_user_session("test_user")
# 	assert token is not None
#
#
# # Test the remove_sql_active_session method
# @pytest.mark.asyncio
# async def test_remove_sql_active_session(adapter_with_db):
# 	await adapter_with_db.set_sql_active_session("test_user", "test_token")
# 	result = await adapter_with_db.remove_sql_active_session("test_user")
# 	assert result is True
#
#
# # Test the remove_sql_user_session method
# @pytest.mark.asyncio
# async def test_remove_sql_user_session(adapter_with_db):
# 	await adapter_with_db.set_sql_user_session("test_user", "test_token")
# 	result = await adapter_with_db.remove_sql_user_session("test_user")
# 	assert result is True
#
#
# # Test the clear_failed_password_attempts method
# @pytest.mark.asyncio
# async def test_clear_failed_password_attempts(adapter_with_db):
# 	await adapter_with_db.set_failed_password_attempt_count("test_user", 3)
# 	result = await adapter_with_db.clear_failed_password_attempts("test_user")
# 	assert result is True
#
#
# # Test the get_failed_password_attempt_count method
# @pytest.mark.asyncio
# async def test_get_failed_password_attempt_count(adapter_with_db):
# 	await adapter_with_db.set_failed_password_attempt_count("test_user", 3)
# 	count = await adapter_with_db.get_failed_password_attempt_count("test_user")
# 	assert count == 3
#
#
# # Test the set_failed_password_attempt_count method
# @pytest.mark.asyncio
# async def test_set_failed_password_attempt_count(adapter_with_db):
# 	result = await adapter_with_db.set_failed_password_attempt_count("test_user", 2)
# 	assert result is True
