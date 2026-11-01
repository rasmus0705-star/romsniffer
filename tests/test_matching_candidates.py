import unittest

import rom_matching


class CandidateMatchingTests(unittest.TestCase):
    def tearDown(self):
        rom_matching.set_manual_pairs({})

    def test_candidates_keep_name_matches_and_manual_decisions(self):
        products = [
            {
                "name": "Ron Zacapa Centenario 23",
                "brand": "Zacapa",
                "age": "23 år",
                "volume_cl": 70,
                "abv": 40,
                "editions": set(),
                "shop_name": "Shop A",
                "url": "https://example.test/zacapa-a",
                "price": 500,
            },
            {
                "name": "Appleton Estate Signature Blend",
                "brand": "Appleton",
                "age": None,
                "volume_cl": 70,
                "abv": 40,
                "editions": set(),
                "shop_name": "Shop B",
                "url": "https://example.test/appleton",
                "price": 300,
            },
            {
                "name": "Zacapa Centenario 23 years old",
                "brand": "Zacapa",
                "age": "23 år",
                "volume_cl": 70,
                "abv": 40,
                "editions": set(),
                "shop_name": "Shop C",
                "url": "https://example.test/zacapa-c",
                "price": 510,
            },
            {
                "name": "Manual Pair Alpha",
                "shop_name": "Shop D",
                "url": "https://example.test/manual-alpha",
                "price": 100,
            },
            {
                "name": "Completely Different Beta",
                "shop_name": "Shop E",
                "url": "https://example.test/manual-beta",
                "price": 101,
            },
            {
                "name": "Manual Separate Gamma",
                "shop_name": "Shop F",
                "url": "https://example.test/manual-gamma",
                "price": 100,
            },
            {
                "name": "Unrelated Delta",
                "shop_name": "Shop G",
                "url": "https://example.test/manual-delta",
                "price": 101,
            },
        ]
        rom_matching.set_manual_pairs({
            tuple(sorted((products[3]["url"], products[4]["url"]))): "sammen",
            tuple(sorted((products[5]["url"], products[6]["url"]))): "adskilt",
        })

        groups, stats = rom_matching.group_products(products, verbose=False)
        by_urls = {
            frozenset(product["url"] for product in group)
            for group in groups
        }

        self.assertIn(
            frozenset((products[0]["url"], products[2]["url"])),
            by_urls,
        )
        self.assertIn(
            frozenset((products[3]["url"], products[4]["url"])),
            by_urls,
        )
        self.assertIn(frozenset((products[5]["url"],)), by_urls)
        self.assertIn(frozenset((products[6]["url"],)), by_urls)
        self.assertEqual(len(groups), 5)
        self.assertLess(stats["candidate_group_checks"], len(products) * (len(products) - 1) // 2)


if __name__ == "__main__":
    unittest.main()
