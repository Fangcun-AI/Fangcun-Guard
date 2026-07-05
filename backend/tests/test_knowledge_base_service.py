from pathlib import Path

from services.knowledge_base_service import KnowledgeBaseStore


def store(tmp_path):
    service = KnowledgeBaseStore.__new__(KnowledgeBaseStore)
    service.storage_path = tmp_path
    service.similarity_threshold = 0.7
    service.max_results = 5
    return service


def test_parse_jsonl_filters_invalid_records(tmp_path):
    service = store(tmp_path)
    pairs = service.parse_jsonl_file(
        b'{"questionid":" 1 ","question":" hello ","answer":" world "}\n'
        b'{"questionid":"2","question":"","answer":"ignored"}\n'
        b'not-json\n'
    )
    assert pairs == [{"questionid": "1", "question": "hello", "answer": "world"}]


def test_save_original_file_strips_directory_components(tmp_path):
    service = store(tmp_path)
    path = Path(service.save_original_file(b"data", 7, "../../outside.jsonl"))
    assert path == tmp_path / "kb_7_outside.jsonl"
    assert path.read_bytes() == b"data"


def test_delete_files_only_removes_selected_knowledge_base(tmp_path):
    service = store(tmp_path)
    own = tmp_path / "kb_7_original.jsonl"
    other = tmp_path / "kb_8_original.jsonl"
    own.write_text("own")
    other.write_text("other")
    service.delete_knowledge_base_files(7)
    assert not own.exists()
    assert other.exists()


def test_file_info_reads_vector_metadata(tmp_path):
    service = store(tmp_path)
    service._write_pickle(tmp_path / "kb_7_vectors.pkl", {"total_pairs": 3})
    assert service.get_file_info(7)["total_qa_pairs"] == 3
