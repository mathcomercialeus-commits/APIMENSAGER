-- Replace hash/salt with generated values in production.
insert into settings (id, timezone, integrations)
values (1, 'America/Sao_Paulo', '{"instagram":{"mode":"mock","connected":false},"facebook":{"mode":"mock","connected":false},"whatsapp":{"mode":"mock","connected":false}}')
on conflict (id) do nothing;
