from pathlib import Path

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, Column, Integer, String, Text, Numeric, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from sqlalchemy.exc import IntegrityError


DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/materials_sections_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Material(Base):
    __tablename__ = "materials"

    material_id = Column(Integer, primary_key=True, index=True)
    material_name = Column(String(100), nullable=False)
    description = Column(Text)
    characteristics = Column(Text)
    strength_mpa = Column(Numeric(10, 2))
    hardness_hb = Column(Numeric(10, 2))
    poisson_ratio = Column(Numeric(4, 3))
    young_modulus_gpa = Column(Numeric(10, 2))

    sections = relationship("Section", back_populates="material")
    beams = relationship("Beam", back_populates="material")


class SectionType(Base):
    __tablename__ = "section_types"

    section_type_id = Column(Integer, primary_key=True, index=True)
    section_type_name = Column(String(100), nullable=False)
    section_type_desc = Column(Text)

    sections = relationship("Section", back_populates="section_type")


class Section(Base):
    __tablename__ = "sections"

    section_id = Column(Integer, primary_key=True, index=True)
    section_type_id = Column(Integer, ForeignKey("section_types.section_type_id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.material_id"), nullable=False)
    section_name = Column(String(100), nullable=False)
    notes = Column(Text)

    section_type = relationship("SectionType", back_populates="sections")
    material = relationship("Material", back_populates="sections")
    beams = relationship("Beam", back_populates="section")


class Beam(Base):
    __tablename__ = "beams"

    beam_id = Column(Integer, primary_key=True, index=True)
    beam_name = Column(String(100), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.section_id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.material_id"), nullable=False)
    length_m = Column(Numeric(10, 2), nullable=False)  # ВАЖНО: как в твоём SQL
    notes = Column(Text)

    section = relationship("Section", back_populates="beams")
    material = relationship("Material", back_populates="beams")


def norm_text(s: str | None) -> str | None:
    """Пустые строки -> None, иначе strip."""
    if s is None:
        return None
    v = s.strip()
    return v if v else None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Materials / Sections / Beams UI")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/sections", status_code=303)



@app.get("/sections", response_class=HTMLResponse)
def list_sections(request: Request, db: Session = Depends(get_db)):
    sections = (
        db.query(Section)
        .join(Section.section_type)
        .join(Section.material)
        .order_by(Section.section_id)
        .all()
    )
    return templates.TemplateResponse(
        "sections_list.html",
        {"request": request, "sections": sections, "title": "Сечения"},
    )


@app.get("/sections/new", response_class=HTMLResponse)
def new_section_form(request: Request, db: Session = Depends(get_db)):
    section_types = db.query(SectionType).order_by(SectionType.section_type_name).all()
    materials = db.query(Material).order_by(Material.material_name).all()
    return templates.TemplateResponse(
        "section_form.html",
        {
            "request": request,
            "section_types": section_types,
            "materials": materials,
            "title": "Добавить сечение",
        },
    )


@app.post("/sections/new")
def create_section(
    section_name: str = Form(...),
    section_type_id: int = Form(...),
    material_id: int = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    section = Section(
        section_name=section_name.strip(),
        section_type_id=section_type_id,
        material_id=material_id,
        notes=norm_text(notes),
    )
    db.add(section)
    db.commit()
    return RedirectResponse(url="/sections", status_code=303)


@app.post("/sections/{section_id}/delete")
def delete_section(section_id: int, db: Session = Depends(get_db)):
    section = db.query(Section).filter(Section.section_id == section_id).first()
    if section is None:
        raise HTTPException(status_code=404, detail="Сечение не найдено")

    db.delete(section)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # RESTRICT: если сечение используется в beams
        raise HTTPException(status_code=400, detail="Нельзя удалить: сечение используется в балках")

    return RedirectResponse(url="/sections", status_code=303)


@app.get("/materials", response_class=HTMLResponse)
def list_materials(request: Request, db: Session = Depends(get_db)):
    materials = db.query(Material).order_by(Material.material_id).all()
    return templates.TemplateResponse(
        "materials_list.html",
        {"request": request, "materials": materials, "title": "Материалы"},
    )


@app.get("/materials/new", response_class=HTMLResponse)
def new_material_form(request: Request):
    return templates.TemplateResponse(
        "material_form.html",
        {"request": request, "title": "Добавить материал"},
    )


@app.post("/materials/new")
def create_material(
    material_name: str = Form(...),
    description: str | None = Form(None),
    characteristics: str | None = Form(None),
    strength_mpa: float | None = Form(None),
    hardness_hb: float | None = Form(None),
    poisson_ratio: float | None = Form(None),
    young_modulus_gpa: float | None = Form(None),
    db: Session = Depends(get_db),
):
    m = Material(
        material_name=material_name.strip(),
        description=norm_text(description),
        characteristics=norm_text(characteristics),
        strength_mpa=strength_mpa,
        hardness_hb=hardness_hb,
        poisson_ratio=poisson_ratio,
        young_modulus_gpa=young_modulus_gpa,
    )
    db.add(m)
    db.commit()
    return RedirectResponse(url="/materials", status_code=303)


@app.post("/materials/{material_id}/delete")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    m = db.query(Material).filter(Material.material_id == material_id).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Материал не найден")

    db.delete(m)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # RESTRICT: если материал используется в sections или beams
        raise HTTPException(status_code=400, detail="Нельзя удалить: материал используется в сечениях/балках")

    return RedirectResponse(url="/materials", status_code=303)



@app.get("/section-types", response_class=HTMLResponse)
def list_section_types(request: Request, db: Session = Depends(get_db)):
    types_ = db.query(SectionType).order_by(SectionType.section_type_id).all()
    return templates.TemplateResponse(
        "section_types_list.html",
        {"request": request, "section_types": types_, "title": "Типы сечений"},
    )


@app.get("/section-types/new", response_class=HTMLResponse)
def new_section_type_form(request: Request):
    return templates.TemplateResponse(
        "section_type_form.html",
        {"request": request, "title": "Добавить тип сечения"},
    )


@app.post("/section-types/new")
def create_section_type(
    section_type_name: str = Form(...),
    section_type_desc: str | None = Form(None),
    db: Session = Depends(get_db),
):
    t = SectionType(
        section_type_name=section_type_name.strip(),
        section_type_desc=norm_text(section_type_desc),
    )
    db.add(t)
    db.commit()
    return RedirectResponse(url="/section-types", status_code=303)


@app.post("/section-types/{section_type_id}/delete")
def delete_section_type(section_type_id: int, db: Session = Depends(get_db)):
    t = db.query(SectionType).filter(SectionType.section_type_id == section_type_id).first()
    if t is None:
        raise HTTPException(status_code=404, detail="Тип сечения не найден")

    db.delete(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # RESTRICT: если тип используется в sections
        raise HTTPException(status_code=400, detail="Нельзя удалить: тип используется в сечениях")

    return RedirectResponse(url="/section-types", status_code=303)


@app.get("/beams", response_class=HTMLResponse)
def list_beams(request: Request, db: Session = Depends(get_db)):
    beams = (
        db.query(Beam)
        .join(Beam.section)
        .join(Beam.material)
        .order_by(Beam.beam_id)
        .all()
    )
    return templates.TemplateResponse(
        "beams_list.html",
        {"request": request, "beams": beams, "title": "Балки"},
    )


@app.get("/beams/new", response_class=HTMLResponse)
def new_beam_form(request: Request, db: Session = Depends(get_db)):
    sections = db.query(Section).order_by(Section.section_name).all()
    materials = db.query(Material).order_by(Material.material_name).all()
    return templates.TemplateResponse(
        "beam_form.html",
        {"request": request, "sections": sections, "materials": materials, "title": "Добавить балку"},
    )


@app.post("/beams/new")
def create_beam(
    beam_name: str = Form(...),
    section_id: int = Form(...),
    material_id: int = Form(...),
    length_m: float = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if length_m <= 0:
        raise HTTPException(status_code=400, detail="Длина должна быть больше 0")

    b = Beam(
        beam_name=beam_name.strip(),
        section_id=section_id,
        material_id=material_id,
        length_m=length_m,
        notes=norm_text(notes),
    )
    db.add(b)
    db.commit()
    return RedirectResponse(url="/beams", status_code=303)


@app.post("/beams/{beam_id}/delete")
def delete_beam(beam_id: int, db: Session = Depends(get_db)):
    b = db.query(Beam).filter(Beam.beam_id == beam_id).first()
    if b is None:
        raise HTTPException(status_code=404, detail="Балка не найдена")

    db.delete(b)
    db.commit()
    return RedirectResponse(url="/beams", status_code=303)

@app.get("/api/materials")
def api_materials(db: Session = Depends(get_db)):
    materials = db.query(Material).all()
    return [
        {
            "material_id": m.material_id,
            "material_name": m.material_name,
            "description": m.description,
            "strength_mpa": float(m.strength_mpa) if m.strength_mpa is not None else None,
            "hardness_hb": float(m.hardness_hb) if m.hardness_hb is not None else None,
            "young_modulus_gpa": float(m.young_modulus_gpa) if m.young_modulus_gpa is not None else None,
        }
        for m in materials
    ]


@app.get("/api/sections")
def api_sections(db: Session = Depends(get_db)):
    sections = db.query(Section).join(Section.section_type).join(Section.material).all()
    return [
        {
            "section_id": s.section_id,
            "section_name": s.section_name,
            "section_type": s.section_type.section_type_name,
            "material": s.material.material_name,
            "notes": s.notes,
        }
        for s in sections
    ]
