import pathlib
import re
import unittest

HERE = pathlib.Path(__file__).resolve().parent
AGENTS = HERE / 'opencode' / 'agent-json'
SKILLS = HERE / 'opencode' / 'skills'
OWN = {'code': 'code-solutions', 'data-analysis': 'analysis-answers', 'diagram': 'diagram-mermaid',
       'docx': 'docx-writing', 'map': 'map-geojson', 'scene-3d': 'scene-3d-catalog', 'slides': 'slides-writing',
       'spreadsheet': 'spreadsheet-ops'}


def frontmatter(path):
    text = path.read_text()
    assert text.startswith('---\n'), path
    return text.split('---\n', 2)[1]


class Skills(unittest.TestCase):
    def test_every_agent_has_its_skill(self):
        self.assertEqual({p.stem for p in AGENTS.glob('*.md')}, set(OWN))
        self.assertEqual({p.name for p in SKILLS.iterdir()}, set(OWN.values()))

    def test_skill_name_matches_its_folder(self):
        for folder in SKILLS.iterdir():
            fm = frontmatter(folder / 'SKILL.md')
            name = re.search(r'^name: (\S+)$', fm, re.M)[1]
            self.assertEqual(name, folder.name)
            self.assertRegex(name, r'^[a-z0-9]+(-[a-z0-9]+)*$')
            self.assertTrue(re.search(r'^description: .+', fm, re.M), folder.name)

    def test_skills_stay_short(self):
        for folder in SKILLS.iterdir():
            self.assertLessEqual(len((folder / 'SKILL.md').read_text().splitlines()), 150, folder.name)

    def test_agent_allows_only_its_own_skill(self):
        for agent, skill in OWN.items():
            fm = frontmatter(AGENTS / f'{agent}.md')
            block = re.search(r'^  skill:\n((?:    .+\n)+)', fm, re.M)
            self.assertIsNotNone(block, agent)
            rules = dict(re.findall(r'^    "?([^":\s]+)"?: (\w+)$', block[1], re.M))
            self.assertEqual(rules, {'*': 'deny', skill: 'allow'}, agent)

    def test_prompt_tells_the_agent_to_load_it(self):
        for agent, skill in OWN.items():
            body = (AGENTS / f'{agent}.md').read_text().split('---\n', 2)[2]
            self.assertIn(f'load the `{skill}` skill', body.lstrip().splitlines()[0], agent)

    def test_docker_mounts_skills_read_only(self):
        import sys
        sys.path.insert(0, str(HERE))
        from run import docker_argv
        argv = docker_argv('n', pathlib.Path('/w'), 'docx', 'cc/x', 'p')
        mount = [a for a in argv if a.endswith('/skills:ro')]
        self.assertEqual(len(mount), 1)
        self.assertTrue(mount[0].endswith('/home/runner/.config/opencode/skills:ro'))


if __name__ == '__main__':
    unittest.main()
