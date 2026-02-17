# tests/test_storage.py
from pathlib import Path

import pytest
from PIL import Image

from chroniclemap.core.models import FilterType
from chroniclemap.core.models import GameDate as date
from chroniclemap.core.models import new_campaign
from chroniclemap.storage.manager import (
    StorageManager,
    create_campaign_on_disk,
    import_image_into_campaign,
    load_campaign_from_disk,
    save_campaign_to_disk,
)


def test_create_save_load_campaign(tmp_path):
    base = tmp_path
    camp = new_campaign("camp-a", path=None)
    root = create_campaign_on_disk(base, camp)
    assert (root / "metadata.json").exists()
    loaded = load_campaign_from_disk(root)
    assert loaded.name == camp.name
    # update and save
    loaded.notes = "hello"
    save_campaign_to_disk(loaded)
    reloaded = load_campaign_from_disk(root)
    assert reloaded.notes == "hello"


def test_import_image_creates_files_and_metadata(tmp_path):
    base = tmp_path
    camp = new_campaign("camp-b", path=None)
    _root = create_campaign_on_disk(base, camp)

    # create a simple image file to import
    src = base / "tmp_img.png"
    im = Image.new("RGBA", (800, 600), color=(123, 222, 111, 255))
    im.save(src)

    snap = import_image_into_campaign(
        campaign=camp,
        src_path=src,
        filter_type=FilterType.REALMS,
        date_str="1444-11-11",
    )
    # check files exist
    dest = Path(snap.path)
    assert dest.exists()
    # thumbnail exists
    thumb = Path(snap.thumbnail)
    assert thumb.exists()
    # metadata contains snapshot
    loaded = load_campaign_from_disk(Path(camp.path))
    assert any(
        s["date"].startswith("1444-11-11") for s in loaded.to_dict()["snapshots"]
    )


# ==================== StorageManager Tests ====================


def test_storage_manager_init_creates_base_dir(tmp_path):
    """测试 StorageManager 初始化时会创建基础目录"""
    base = tmp_path / "new_storage"
    assert not base.exists()
    _manager = StorageManager(base)
    assert base.exists()
    assert base.is_dir()


def test_storage_manager_create_campaign(tmp_path):
    """测试通过 StorageManager 创建活动"""
    manager = StorageManager(tmp_path)

    camp = manager.create_campaign("test-campaign")

    # 验证返回的对象
    assert camp.name == "test-campaign"
    assert camp.path == str(tmp_path / "test-campaign")

    # 验证磁盘结构
    camp_dir = tmp_path / "test-campaign"
    assert (camp_dir / "metadata.json").exists()
    assert (camp_dir / "maps").is_dir()
    assert (camp_dir / "thumbnails").is_dir()


def test_storage_manager_list_campaigns(tmp_path):
    """测试列出所有活动"""
    manager = StorageManager(tmp_path)

    # 初始为空
    assert list(manager.list_campaigns()) == []

    # 创建多个活动
    manager.create_campaign("alpha")
    manager.create_campaign("beta")
    manager.create_campaign("gamma")

    # 验证列表包含所有创建的活动（不强制要求只有3个，可能有其他目录）
    campaigns = list(manager.list_campaigns())
    assert "alpha" in campaigns
    assert "beta" in campaigns
    assert "gamma" in campaigns

    # 验证排序（假设按字母排序）
    assert campaigns == sorted(campaigns)


def test_storage_manager_load_campaign_by_name(tmp_path):
    """测试通过名称加载活动"""
    manager = StorageManager(tmp_path)
    created = manager.create_campaign("loadable")
    created.notes = "Test notes"
    manager.save_campaign(created)

    # 通过名称加载
    loaded = manager.load_campaign("loadable")
    assert loaded.name == "loadable"
    assert loaded.notes == "Test notes"
    assert loaded.path == str(tmp_path / "loadable")


def test_storage_manager_load_campaign_by_path(tmp_path):
    """测试通过路径加载活动"""
    manager = StorageManager(tmp_path)
    manager.create_campaign("path-test")

    # 通过绝对路径加载
    camp_path = tmp_path / "path-test"
    loaded = manager.load_campaign(camp_path)
    assert loaded.name == "path-test"

    # 通过字符串路径加载
    loaded2 = manager.load_campaign(str(camp_path))
    assert loaded2.name == "path-test"


def test_storage_manager_load_nonexistent_campaign(tmp_path):
    """测试加载不存在的活动应抛出异常"""
    manager = StorageManager(tmp_path)

    with pytest.raises(FileNotFoundError, match="not found"):
        manager.load_campaign("ghost-campaign")

    with pytest.raises(FileNotFoundError):
        manager.load_campaign(tmp_path / "nonexistent" / "path")


def test_storage_manager_save_campaign_updates_metadata(tmp_path):
    """测试通过 StorageManager 保存活动元数据"""
    manager = StorageManager(tmp_path)
    camp = manager.create_campaign("save-test")

    # 修改并保存（只使用 Campaign 实际存在的字段）
    original_modified = camp.modified_at
    camp.notes = "New notes for testing"
    manager.save_campaign(camp)

    # 重新加载验证
    reloaded = manager.load_campaign("save-test")
    assert reloaded.notes == "New notes for testing"
    assert reloaded.modified_at == original_modified


def test_storage_manager_import_image(tmp_path):
    """测试通过 StorageManager 导入图片"""
    manager = StorageManager(tmp_path)
    camp = manager.create_campaign("import-campaign")

    # 创建测试图片
    src = tmp_path / "map_image.png"
    img = Image.new("RGBA", (1024, 768), color=(255, 0, 0, 255))
    img.save(src)

    # 导入图片
    snap = manager.import_image(
        campaign=camp,
        src_path=src,
        filter_type=FilterType.REALMS,
        date_str="1066-10-14",
    )

    # 验证返回的 snapshot - date 是 date 对象，不是字符串
    assert snap.date == date(1066, 10, 14)  # 使用 date 对象比较
    assert snap.filter_type == FilterType.REALMS
    assert snap.path is not None
    assert snap.thumbnail is not None

    # 验证文件存在
    assert Path(snap.path).exists()
    assert Path(snap.thumbnail).exists()

    # 验证在 maps 目录下的 filter 子目录中
    assert "maps" in snap.path
    assert "realms" in snap.path.lower()


def test_storage_manager_import_image_with_string_filter(tmp_path):
    """测试使用字符串类型的 filter_type 导入"""
    manager = StorageManager(tmp_path)
    camp = manager.create_campaign("import-str")

    src = tmp_path / "test.png"
    Image.new("RGB", (100, 100), color="blue").save(src)

    # 使用字符串
    snap = manager.import_image(camp, src, "CUSTOM", "2024-01-01")
    assert snap.filter_type == FilterType.CUSTOM


def test_storage_manager_find_snapshot_by_id(tmp_path):
    """测试通过 ID 查找快照"""
    manager = StorageManager(tmp_path)
    camp = manager.create_campaign("find-snapshot")

    # 创建两个图片
    src1 = tmp_path / "snap1.png"
    src2 = tmp_path / "snap2.png"
    Image.new("RGB", (100, 100), color="red").save(src1)
    Image.new("RGB", (100, 100), color="blue").save(src2)

    snap1 = manager.import_image(camp, src1, FilterType.REALMS, "1000-01-01")
    snap2 = manager.import_image(camp, src2, FilterType.REALMS, "2000-12-31")

    # 测试查找存在的 - date 是 date 对象
    found1 = manager.find_snapshot_by_id(camp, snap1.id)
    assert found1 is not None
    assert found1.id == snap1.id
    assert found1.date == date(1000, 1, 1)  # 改为 date 对象

    found2 = manager.find_snapshot_by_id(camp, snap2.id)
    assert found2.id == snap2.id
    assert found2.date == date(2000, 12, 31)  # 同样改为 date 对象

    # 测试查找不存在的
    not_found = manager.find_snapshot_by_id(camp, "invalid-id-12345")
    assert not_found is None


def test_storage_manager_find_snapshot_empty_campaign(tmp_path):
    """测试在空活动中查找快照"""
    manager = StorageManager(tmp_path)
    camp = manager.create_campaign("empty-camp")

    result = manager.find_snapshot_by_id(camp, "any-id")
    assert result is None


def test_storage_manager_full_workflow(tmp_path):
    """测试完整的工作流：创建 -> 导入 -> 保存 -> 加载 -> 查找"""
    manager = StorageManager(tmp_path)

    # 1. 创建活动
    camp = manager.create_campaign("full-workflow")

    # 2. 导入多张图片
    dates = [date(1400, 1, 1), date(1400, 2, 1), date(1400, 3, 1)]
    for i, (color, dt) in enumerate(zip(["red", "green", "blue"], dates)):
        img_path = tmp_path / f"map_{i}.png"
        Image.new("RGB", (200, 200), color=color).save(img_path)
        manager.import_image(
            camp, img_path, FilterType.REALMS, dt.to_iso()  # 使用 ISO 格式字符串
        )

    # 3. 重新加载活动（验证持久化）
    loaded = manager.load_campaign("full-workflow")
    assert len(loaded.snapshots) == 3

    # 4. 查找特定快照 - 注意 date 类型可能是 date 对象或字符串
    original_id = camp.snapshots[1].id
    found = manager.find_snapshot_by_id(loaded, original_id)
    assert found is not None

    # 根据实际类型比较（这里假设是 date 对象）
    assert found.date == date(1400, 2, 1)  # 直接使用 date 对象比较
