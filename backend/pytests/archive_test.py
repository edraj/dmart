# import pytest
# from unittest.mock import patch
# from time import time
# import argparse
# import asyncio
# from archive import redis_doc_to_meta, archive
#
#
# def test_redis_doc_to_meta():
#     mock_record = {
#         "resource_type": "record",
#         "created_at": time(),
#         "updated_at": time(),
#     }
#     expected_keys = ["resource_type", "created_at", "updated_at"]
#     with patch("models.core.Record") as MockRecord:
#         MockRecord.model_fields.keys.return_value = expected_keys
#         MockRecord.model_validate.return_value = mock_record
#         meta = redis_doc_to_meta(mock_record)
#         assert meta == mock_record
#         assert MockRecord.model_fields.keys.call_count == 3
#         MockRecord.model_validate.assert_called_once()
#
# def main():
#     parser = argparse.ArgumentParser(
#         description="Script for archiving records from different spaces and subpaths."
#     )
#     parser.add_argument("space", type=str, help="The name of the space")
#     parser.add_argument("subpath", type=str, help="The subpath within the space")
#     parser.add_argument(
#         "schema",
#         type=str,
#         help="The subpath within the space. Optional, if not provided move everything",
#         nargs="?",
#     )
#     parser.add_argument(
#         "olderthan",
#         type=int,
#         help="The number of day, older than which, the entries will be archived (based on updated_at)",
#     )
#
#     args = parser.parse_args()
#     space = args.space
#     subpath = args.subpath
#     olderthan = args.olderthan
#     schema = args.schema or "meta"
#
#     asyncio.run(archive(space, subpath, schema, olderthan))
#     print("Done.")
#
#
# @pytest.mark.asyncio
# @patch("argparse.ArgumentParser.parse_args")
# @patch("archive.archive")
# async def test_main(mock_archive, mock_parse_args):
#     mock_args = argparse.Namespace(
#         space="space",
#         subpath="subpath",
#         schema="schema",
#         olderthan=1
#     )
#     mock_parse_args.return_value = mock_args
#
#     with patch("asyncio.run") as mock_asyncio_run:
#         mock_asyncio_run.side_effect = lambda x: asyncio.ensure_future(x)
#         main()
#
#     mock_parse_args.assert_called_once()
#     mock_asyncio_run.assert_called_once()
#
# if __name__ == "__main__":
#     pytest.main()