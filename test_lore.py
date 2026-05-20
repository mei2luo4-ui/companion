"""测试角色设定：关系网、字数限制、去掉陪伴师定位"""
import os, sys
os.environ['API_KEY'] = 'test'
sys.path.insert(0, '.')

from backend.companion import build_system_prompt, CHARACTER_LORE, CHARACTER_RELATIONS

CHARS = [
    ('晓柔', '温柔体贴', '温柔低语'),
    ('星澜', '冷艳神秘', '深沉内敛'),
    ('糖糖', '元气少女', '活泼跳脱'),
    ('沐雪', '温婉古典', '古风雅韵'),
    ('凌霄', '御姐霸气', '简洁干练'),
    ('知微', '沉稳知性', '正式得体'),
    ('阿橘', '俏皮搞怪', '亲密随意'),
    ('诗韵', '活泼开朗', '文艺诗意'),
]

PASS = FAIL = 0

for name, personality, style in CHARS:
    p = {'name': name, 'personality': personality, 'speaking_style': style, 'avatar_emoji': ''}
    prompt = build_system_prompt(p, [])
    checks = {
        '有关系网':       '认识的人' in prompt,
        '有背景故事':     '背景故事' in prompt,
        '有平行世界设定': '平行世界' in prompt,
        '有字数限制':     '30字' in prompt,
        '去掉陪伴师':     '情感陪伴伙伴' not in prompt,
        '有3章故事':      len(CHARACTER_LORE.get(name, [])) == 3,
        '有关系描述':     bool(CHARACTER_RELATIONS.get(name)),
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        print(f'[FAIL] {name}: {failed}')
        FAIL += 1
    else:
        print(f'[PASS] {name}')
        PASS += 1

# 检查对立关系是否双向注入
xinglan_prompt = build_system_prompt({'name':'星澜','personality':'冷艳神秘','speaking_style':'深沉内敛','avatar_emoji':''}, [])
zhiwei_prompt  = build_system_prompt({'name':'知微','personality':'沉稳知性','speaking_style':'正式得体','avatar_emoji':''}, [])

if '知微' in xinglan_prompt and '星澜' in zhiwei_prompt:
    print('[PASS] 星澜<->知微 对立关系双向注入')
    PASS += 1
else:
    print('[FAIL] 星澜<->知微 对立关系双向注入缺失')
    FAIL += 1

print(f'\n结果: {PASS} 通过 / {FAIL} 失败')
