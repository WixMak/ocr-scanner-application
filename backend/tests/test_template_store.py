import numpy as np
import pytest
from pydantic import ValidationError

from app.errors import DraftNotFoundError, FieldOutsideImageError, TemplateNotFoundError
from app.schemas import (
    BoundingBox,
    ChoiceOption,
    FieldType,
    PageSize,
    TemplateCreate,
    TemplateField,
    TemplateUpdate,
)
from app.services.template_store import TemplateStore

IMAGE_WIDTH = 400
IMAGE_HEIGHT = 300
SECOND_PAGE_HEIGHT = 500


def make_field(
    key: str = "full_name", *, box: BoundingBox | None = None, page_index: int = 0
) -> TemplateField:
    return TemplateField(
        id=f"id-{key}",
        key=key,
        label="姓名 Full Name",
        field_type=FieldType.TEXT,
        page_index=page_index,
        box=box or BoundingBox(x=10, y=10, width=100, height=40),
    )


def blank_page(height: int = IMAGE_HEIGHT) -> np.ndarray:
    return np.full((height, IMAGE_WIDTH, 3), 255, dtype=np.uint8)


def save_draft(store: TemplateStore) -> str:
    return store.save_draft_images([blank_page()])


def save_two_page_draft(store: TemplateStore) -> str:
    return store.save_draft_images([blank_page(), blank_page(SECOND_PAGE_HEIGHT)])


def test_creates_template_from_draft_and_moves_its_image(template_store: TemplateStore) -> None:
    draft_id = save_draft(template_store)

    template = template_store.create(
        TemplateCreate(name="Enrolment", draft_id=draft_id, fields=[make_field()])
    )

    assert template.pages == [PageSize(image_width=IMAGE_WIDTH, image_height=IMAGE_HEIGHT)]
    assert template_store.get(template.id) == template
    assert [page.shape for page in template_store.load_blank_pages(template)] == [
        (IMAGE_HEIGHT, IMAGE_WIDTH, 3)
    ]
    with pytest.raises(DraftNotFoundError):
        template_store.draft_image_path(draft_id, 0)


def test_creates_template_with_every_page_of_the_draft(template_store: TemplateStore) -> None:
    draft_id = save_two_page_draft(template_store)
    field_on_second_page = make_field(
        box=BoundingBox(x=10, y=400, width=100, height=40), page_index=1
    )

    template = template_store.create(
        TemplateCreate(name="Two pages", draft_id=draft_id, fields=[field_on_second_page])
    )

    assert [page.image_height for page in template.pages] == [IMAGE_HEIGHT, SECOND_PAGE_HEIGHT]
    assert len(template_store.load_blank_pages(template)) == 2
    assert template_store.image_path(template.id, 1).exists()
    with pytest.raises(DraftNotFoundError):
        template_store.draft_image_path(draft_id, 1)


def make_choice_field(option_box: BoundingBox) -> TemplateField:
    return TemplateField(
        id="id-account-type",
        key="account_type",
        label="Account Type",
        field_type=FieldType.CHOICE,
        page_index=0,
        box=BoundingBox(x=10, y=10, width=40, height=40),
        options=[ChoiceOption(id="personal", label="Personal", box=option_box)],
    )


def test_saves_choice_field_with_its_options(template_store: TemplateStore) -> None:
    choice = make_choice_field(BoundingBox(x=10, y=10, width=30, height=30))

    template = template_store.create(
        TemplateCreate(name="Choices", draft_id=save_draft(template_store), fields=[choice])
    )

    assert template_store.get(template.id).fields[0].options == choice.options


def test_rejects_choice_option_outside_the_form_image(template_store: TemplateStore) -> None:
    choice = make_choice_field(BoundingBox(x=390, y=10, width=30, height=30))
    request = TemplateCreate(name="Bad", draft_id=save_draft(template_store), fields=[choice])

    with pytest.raises(FieldOutsideImageError):
        template_store.create(request)


def test_choice_field_needs_at_least_one_option() -> None:
    choice_without_options = {**make_field().model_dump(), "field_type": FieldType.CHOICE}

    with pytest.raises(ValidationError, match="at least one option"):
        TemplateField.model_validate(choice_without_options)


def test_only_choice_fields_can_have_options() -> None:
    option = ChoiceOption(id="joint", label="Joint", box=BoundingBox(x=1, y=1, width=5, height=5))
    text_with_options = {**make_field().model_dump(), "options": [option]}

    with pytest.raises(ValidationError, match="Only choice fields"):
        TemplateField.model_validate(text_with_options)


def test_rejects_field_outside_the_form_image(template_store: TemplateStore) -> None:
    outside = make_field(box=BoundingBox(x=350, y=10, width=100, height=40))

    with pytest.raises(FieldOutsideImageError):
        template_store.create(
            TemplateCreate(name="Bad", draft_id=save_draft(template_store), fields=[outside])
        )


@pytest.mark.parametrize(
    "field",
    [
        pytest.param(make_field(page_index=2), id="page that does not exist"),
        pytest.param(
            make_field(box=BoundingBox(x=10, y=400, width=100, height=40), page_index=0),
            id="below the end of a shorter page",
        ),
    ],
)
def test_rejects_field_that_is_not_on_its_page(
    template_store: TemplateStore, field: TemplateField
) -> None:
    request = TemplateCreate(
        name="Bad", draft_id=save_two_page_draft(template_store), fields=[field]
    )

    with pytest.raises(FieldOutsideImageError):
        template_store.create(request)


def test_updates_name_and_fields(template_store: TemplateStore) -> None:
    template = template_store.create(
        TemplateCreate(name="Old", draft_id=save_draft(template_store), fields=[make_field()])
    )

    updated = template_store.update(
        template.id, TemplateUpdate(name="New", fields=[make_field("phone")])
    )

    assert updated.name == "New"
    assert [field.key for field in template_store.get(template.id).fields] == ["phone"]
    assert updated.updated_at >= template.updated_at
    assert updated.created_at == template.created_at


def test_update_rejects_field_moved_to_a_missing_page(template_store: TemplateStore) -> None:
    template = template_store.create(
        TemplateCreate(name="Old", draft_id=save_draft(template_store), fields=[])
    )
    request = TemplateUpdate(name="Old", fields=[make_field(page_index=1)])

    with pytest.raises(FieldOutsideImageError):
        template_store.update(template.id, request)


def test_lists_summaries_newest_first(template_store: TemplateStore) -> None:
    first = template_store.create(
        TemplateCreate(name="First", draft_id=save_draft(template_store), fields=[])
    )
    second = template_store.create(
        TemplateCreate(name="Second", draft_id=save_draft(template_store), fields=[make_field()])
    )

    summaries = template_store.list_summaries()

    assert [summary.id for summary in summaries] == [second.id, first.id]
    assert summaries[0].field_count == 1


def test_deletes_template_and_every_page_image(template_store: TemplateStore) -> None:
    template = template_store.create(
        TemplateCreate(name="Gone", draft_id=save_two_page_draft(template_store), fields=[])
    )

    template_store.delete(template.id)

    with pytest.raises(TemplateNotFoundError):
        template_store.get(template.id)
    for page_index in range(2):
        with pytest.raises(TemplateNotFoundError):
            template_store.image_path(template.id, page_index)
    with pytest.raises(TemplateNotFoundError):
        template_store.delete(template.id)


@pytest.mark.parametrize("unsafe_id", ["../secrets", "ABC", "0" * 31])
def test_rejects_ids_that_are_not_stored_ids(template_store: TemplateStore, unsafe_id: str) -> None:
    with pytest.raises(TemplateNotFoundError):
        template_store.get(unsafe_id)
    with pytest.raises(DraftNotFoundError):
        template_store.draft_image_path(unsafe_id, 0)


def test_unreadable_template_image_is_reported_as_not_found(
    template_store: TemplateStore,
) -> None:
    template = template_store.create(
        TemplateCreate(name="Corrupt", draft_id=save_draft(template_store), fields=[])
    )
    template_store.image_path(template.id, 0).write_bytes(b"not a png")

    with pytest.raises(TemplateNotFoundError):
        template_store.load_blank_pages(template)


def test_unreadable_draft_image_is_reported_as_not_found(template_store: TemplateStore) -> None:
    draft_id = save_draft(template_store)
    template_store.draft_image_path(draft_id, 0).write_bytes(b"not a png")

    with pytest.raises(DraftNotFoundError):
        template_store.create(TemplateCreate(name="Corrupt", draft_id=draft_id, fields=[]))


def test_rejects_duplicate_field_keys() -> None:
    with pytest.raises(ValueError, match="unique"):
        TemplateUpdate(name="Dupes", fields=[make_field("phone"), make_field("phone")])
