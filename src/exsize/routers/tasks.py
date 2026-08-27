from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from exsize.database import get_db
from exsize.deps import get_current_user, has_sizepass
from exsize.models import AppSetting, AvatarItem, Task, Transaction, User
from exsize.routers.gamification import compute_level

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    name: str
    description: str
    exbucks: int
    assigned_to: int
    day_of_week: str | None = None
    due_date: date | None = None


class TaskResponse(BaseModel):
    id: int
    name: str
    description: str
    exbucks: int
    status: str
    assigned_to: int
    day_of_week: str | None = None
    due_date: date | None = None
    photo_url: str | None = None
    avatar_icon: str | None = None
    avatar_background: str | None = None

    model_config = {"from_attributes": True}


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Only parents can create tasks")
    if user.family_id is None:
        raise HTTPException(status_code=400, detail="Must be in a family")
    child = db.query(User).filter(
        User.id == body.assigned_to,
        User.family_id == user.family_id,
        User.role == "child",
    ).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found in your family")
    max_setting = db.query(AppSetting).filter(AppSetting.key == "max_exbucks_per_task").first()
    if max_setting and body.exbucks > int(max_setting.value):
        raise HTTPException(status_code=400, detail=f"ExBucks exceeds the max limit of {max_setting.value}")
    task = Task(
        name=body.name,
        description=body.description,
        exbucks=body.exbucks,
        assigned_to=body.assigned_to,
        family_id=user.family_id,
        created_by=user.id,
        day_of_week=body.day_of_week,
        due_date=body.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskResponse])
def list_tasks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.family_id is None:
        raise HTTPException(status_code=400, detail="Must be in a family")
    query = db.query(Task).filter(Task.family_id == user.family_id)
    if user.role == "child":
        query = query.filter(Task.assigned_to == user.id)
    tasks = query.all()

    # Collect avatar data for assigned children
    child_ids = {t.assigned_to for t in tasks}
    children = {u.id: u for u in db.query(User).filter(User.id.in_(child_ids)).all()} if child_ids else {}
    avatar_ids = set()
    for c in children.values():
        if c.equipped_icon_id:
            avatar_ids.add(c.equipped_icon_id)
        if c.equipped_background_id:
            avatar_ids.add(c.equipped_background_id)
    avatars = {a.id: a for a in db.query(AvatarItem).filter(AvatarItem.id.in_(avatar_ids)).all()} if avatar_ids else {}

    result = []
    for t in tasks:
        child = children.get(t.assigned_to)
        icon = avatars.get(child.equipped_icon_id) if child and child.equipped_icon_id else None
        bg = avatars.get(child.equipped_background_id) if child and child.equipped_background_id else None
        result.append(TaskResponse(
            id=t.id, name=t.name, description=t.description, exbucks=t.exbucks,
            status=t.status, assigned_to=t.assigned_to, day_of_week=t.day_of_week,
            due_date=t.due_date,
            photo_url=t.photo_url,
            avatar_icon=icon.value if icon else None,
            avatar_background=bg.value if bg else None,
        ))
    return result


class TaskEditRequest(BaseModel):
    name: str
    description: str
    exbucks: int
    assigned_to: int
    day_of_week: str | None = None
    due_date: date | None = None


def _get_family_task(task_id: int, user: User, db: Session) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.family_id == user.family_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskResponse)
def edit_task(task_id: int, body: TaskEditRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Only parents can edit tasks")
    task = _get_family_task(task_id, user, db)
    if task.status in ("completed", "approved"):
        raise HTTPException(status_code=409, detail="Cannot edit a completed or approved task")
    child = db.query(User).filter(
        User.id == body.assigned_to,
        User.family_id == user.family_id,
        User.role == "child",
    ).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found in your family")
    max_setting = db.query(AppSetting).filter(AppSetting.key == "max_exbucks_per_task").first()
    if max_setting and body.exbucks > int(max_setting.value):
        raise HTTPException(status_code=400, detail=f"ExBucks exceeds the max limit of {max_setting.value}")
    task.name = body.name
    task.description = body.description
    task.exbucks = body.exbucks
    task.assigned_to = body.assigned_to
    task.day_of_week = body.day_of_week
    task.due_date = body.due_date
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}/accept", response_model=TaskResponse)
def accept_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "child":
        raise HTTPException(status_code=403, detail="Only children can accept tasks")
    task = _get_family_task(task_id, user, db)
    if task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Task not assigned to you")
    if task.status != "assigned":
        raise HTTPException(status_code=409, detail="Task is not in assigned state")
    task.status = "accepted"
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Only parents can delete tasks")
    task = _get_family_task(task_id, user, db)
    db.delete(task)
    db.commit()


class TaskCompleteRequest(BaseModel):
    photo_url: str | None = None


@router.patch("/{task_id}/complete", response_model=TaskResponse)
def complete_task(task_id: int, body: TaskCompleteRequest | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "child":
        raise HTTPException(status_code=403, detail="Only children can complete tasks")
    task = _get_family_task(task_id, user, db)
    if task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Task not assigned to you")
    if task.status != "accepted":
        raise HTTPException(status_code=409, detail="Task is not in accepted state")
    photo_url = body.photo_url if body else None
    if photo_url:
        if not has_sizepass(user.family_id, db):
            raise HTTPException(status_code=403, detail="Photo attachments require SizePass. Upgrade to attach photos.")
        task.photo_url = photo_url
    task.status = "completed"
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}/approve", response_model=TaskResponse)
def approve_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Only parents can approve tasks")
    task = _get_family_task(task_id, user, db)
    if task.status != "completed":
        raise HTTPException(status_code=409, detail="Task is not in completed state")
    task.status = "approved"
    child = db.query(User).filter(User.id == task.assigned_to).first()
    child.exbucks_balance += task.exbucks
    child.xp += task.exbucks
    child.level = compute_level(child.xp)
    # Streak: check if all tasks for this day_of_week are now approved
    if task.day_of_week:
        sibling_tasks = db.query(Task).filter(
            Task.assigned_to == child.id,
            Task.day_of_week == task.day_of_week,
        ).all()
        if all(t.status == "approved" for t in sibling_tasks):
            today = date.today().isoformat()
            if child.last_completion_date != today:
                child.streak += 1
                child.last_completion_date = today
    txn = Transaction(
        user_id=child.id,
        type="earned",
        amount=task.exbucks,
        description=task.name,
        task_id=task.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}/reject", response_model=TaskResponse)
def reject_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_family_task(task_id, user, db)
    if user.role == "child":
        if task.assigned_to != user.id:
            raise HTTPException(status_code=403, detail="Task not assigned to you")
        if task.status != "assigned":
            raise HTTPException(status_code=409, detail="Task is not in assigned state")
        task.status = "rejected"
    elif user.role == "parent":
        if task.status != "completed":
            raise HTTPException(status_code=409, detail="Task is not in completed state")
        task.status = "assigned"
    else:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.commit()
    db.refresh(task)
    return task
