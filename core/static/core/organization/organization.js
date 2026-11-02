(() => {
  const groups = [
    ['Дирекция', 'Дирекция студенческой организации', 'directorate'],
    ['Аппарат', 'Совет руководителей', 'leadership-council'],
    ['ПК', 'Проектная комиссия', 'project-commission'],
    ['Наука', 'Отдел научного сопровождения', 'science'],
    ['ОСМК', 'Отдел системы менеджмента качества', 'quality'],
    ['ОВД', 'Отдел внутреннего делопроизводства', 'records'],
    ['ОПИ', 'Отдел продвижения и информации', 'communications'],
    ['ОВС', 'Отдел внешних связей', 'external-relations'],
    ['ОВР', 'Отдел внутреннего развития', 'development'],
    ['Советники', 'Группа советников', 'advisers'],
  ];
  const leaders = {
    'Дирекция': ['Кравцов Иван', 'Брезгунова Полина'], 'Аппарат': ['Попкова Екатерина', 'Кравцов Иван', 'Чукина София'],
    'ПК': ['Данилевич Арсений'], 'Наука': ['Кийко Александр'], 'ОСМК': ['Чукина София'],
    'ОВД': ['Братусев Никита'], 'ОВР': ['Дроскова Татьяна'], 'ОВС': ['Ковалева Анна'], 'ОПИ': ['Пакина Злата']
  };
  const roleOverrides = {
    'Кийко Александр': 'Руководитель Отдела научного сопровождения; секретарь НОК «Социальный архитектор»',
    'Попкова Екатерина': 'Управляющий директор — председатель Совета руководителей',
    'Чукина София': 'Руководитель Отдела системы менеджмента качества; секретарь Совета руководителей',
    'Китаев Иван': 'Советник Проектной комиссии', 'Рудницкий Дмитрий': 'Советник Отдела научного сопровождения',
    'Савинова Анна': 'Советник руководителя Отдела продвижения и информации'
  };
  const all = (window.roster || []).map(source => {
    const parts = String(source.name || '').trim().split(/\s+/), key = parts.slice(0, 2).join(' ');
    const role = (roleOverrides[key] || source.role || '')
      .replace(/(^|[^А-Яа-яЁё])ОПиИ(?=$|[^А-Яа-яЁё])/gi, '$1Отдела продвижения и информации')
      .replace(/(^|[^А-Яа-яЁё])ОПИ(?=$|[^А-Яа-яЁё])/g, '$1Отдела продвижения и информации')
      .replace(/(^|[^А-Яа-яЁё])ОВС(?=$|[^А-Яа-яЁё])/g, '$1Отдела внешних связей')
      .replace(/(^|[^А-Яа-яЁё])ОВД(?=$|[^А-Яа-яЁё])/g, '$1Отдела внутреннего делопроизводства')
      .replace(/(^|[^А-Яа-яЁё])ОВР(?=$|[^А-Яа-яЁё])/g, '$1Отдела внутреннего развития')
      .replace(/(^|[^А-Яа-яЁё])ОНС(?=$|[^А-Яа-яЁё])/g, '$1Отдела научного сопровождения')
      .replace(/(^|[^А-Яа-яЁё])ОСМК(?=$|[^А-Яа-яЁё])/g, '$1Отдела системы менеджмента качества')
      .replace(/(^|[^А-Яа-яЁё])ПК(?=$|[^А-Яа-яЁё])/g, '$1Проектной комиссии')
      .replace(/(^|[^А-Яа-яЁё])СР(?=$|[^А-Яа-яЁё])/g, '$1Совета руководителей');
    return {...source, key, surname: parts[0], name: [parts[1], parts[0]].filter(Boolean).join(' '), role,
      units: /советник/i.test(role) ? ['Советники'] : [...new Set(source.units || [])]};
  });
  document.getElementById('org-people-count').textContent = all.length;
  const search = document.getElementById('org-search'), status = document.getElementById('org-status');
  const root = document.getElementById('org-units'), counter = document.getElementById('org-results-count');
  const expand = document.getElementById('org-expand');
  const normalize = value => String(value || '').toLocaleLowerCase('ru').replace(/ё/g, 'е');
  const el = (tag, cls, text) => {const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
  function render() {
    const terms=normalize(search.value).trim().split(/\s+/).filter(Boolean), selected=status.value;
    const matches=all.filter(p=>(selected==='all'||p.status===selected)&&terms.every(term=>normalize([p.name,p.role,...p.units].join(' ')).includes(term)));
    const wasOpen=new Set([...root.querySelectorAll('details[open]')].map(d=>d.dataset.unit));
    root.replaceChildren();
    groups.forEach(([code,title,id],index)=>{
      let members=matches.filter(p=>p.units.includes(code));
      members.sort((a,b)=>{const leader=leaders[code]||[],rank=p=>leader.includes(p.key)?leader.indexOf(p.key):leader.length;return rank(a)-rank(b)||a.surname.localeCompare(b.surname,'ru');});
      if(!members.length)return;
      const detail=el('details','org-unit');detail.id='unit-'+id;detail.dataset.unit=code;detail.open=terms.length>0||wasOpen.has(code);
      const summary=el('summary','org-unit-summary');summary.append(el('span','org-unit-number',code==='Советники'?'+':String(index+1).padStart(2,'0')),el('span','org-unit-name',title),el('span','org-unit-icon','+'));
      const list=el('div','org-people');members.forEach(p=>{const person=el('article','org-person');const initials=p.name.split(/\s+/).slice(0,2).map(x=>x[0]).join('');person.append(el('span','org-person-avatar',initials));const copy=el('span','org-person-copy');copy.append(el('strong','',p.name),el('small','',[p.status,p.role].filter(Boolean).join(' · ')||'Участник'));person.append(copy);if((leaders[code]||[]).includes(p.key))person.classList.add('is-leader');list.append(person);});detail.append(summary,list);root.append(detail);
    });
    const unassigned=matches.filter(p=>!p.units.length);if(unassigned.length){const other=el('section','org-unit org-unassigned');other.append(el('h3','', 'Другие участники команды'));const list=el('div','org-people');unassigned.forEach(p=>{const person=el('article','org-person');person.append(el('span','org-person-avatar',p.name.split(/\s+/).slice(0,2).map(x=>x[0]).join('')));const copy=el('span','org-person-copy');copy.append(el('strong','',p.name),el('small','',[p.status,p.role].filter(Boolean).join(' · ')));person.append(copy);list.append(person);});other.append(list);root.append(other);}
    if(!matches.length)root.append(el('p','org-empty','Никого не нашли. Измените запрос или фильтр.'));
    counter.textContent=`Найдено участников: ${matches.length}`;updateButton();
  }
  function updateButton(){const details=[...root.querySelectorAll('details')],open=details.length&&details.every(d=>d.open);expand.textContent=open?'Свернуть все':'Раскрыть все подразделения';expand.setAttribute('aria-expanded',String(!!open));}
  search.addEventListener('input',render);status.addEventListener('change',render);
  expand.addEventListener('click',()=>{const details=[...root.querySelectorAll('details')],open=details.length&&!details.every(d=>d.open);details.forEach(d=>d.open=!!open);updateButton();});
  root.addEventListener('toggle',updateButton,true);render();
})();
