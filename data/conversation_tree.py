# Define the common structure for 3rdyr, 4thyr, 5thyr, 6thyr
common_year_structure = {
    "template_sid": "HX2c3cd0917bc1346d7b81e0f3fe900e63",
    "next": {
        "I wanna contribute": {
            "template_sid": "HXdec30125048f0c68cfdc96be2e1635cb"
        },
        "I wanna ask": {
            "template_sid": "HXd3d3ec36012acd279b24e2c83614c6e4"
        },
        "I wanna share links": {
            "template_sid": "HXca23bc6cce6664291d327ab40fd2a00f"
        },
    }
}

# Create the "Bachelor of" next dictionary
bachelor_next = {
    "2ndyr": {
        "template_sid": "HXfeceee2bb76ef67b6af576f2a3c8fbbd",
        "next": {
            "I wanna contribute": {
                "template_sid": "HXdec30125048f0c68cfdc96be2e1635cb"
            },
            "Get attachment details": {
                "template_sid": "HX72a87b242b4de6efa9658b2d5bf9d189"
            },
            "I wanna ask": {
                "template_sid": "HXd3d3ec36012acd279b24e2c83614c6e4"
            },
            "I wanna share links": {
                "template_sid": "HXca23bc6cce6664291d327ab40fd2a00f"
            },
        },
    },
}

# Add all other years with the same structure
for yr in ["1styr","3rdyr", "4thyr", "5thyr", "6thyr"]:
    bachelor_next[yr] = common_year_structure

university_structure = {
    "template_sid": [
        "HXbba2f5d603415af88bdfbe77adab8dd3",
        "HXe4891007f818929a556b4649c3d5c6a7",
        # "HX91fa0e6a432bb06fff3c0d0edfa4db76",
        # "HXb83f037d2d23d2e02b9bc86cda52b702",
    ],
    "next": {
        "Bachelor of": {
            "template_sid": "HXb83f037d2d23d2e02b9bc86cda52b702",
            "next": bachelor_next
        }
    },
}

university2_next = {
}
for university2 in ["muast","pamust"]:
    university2_next[university2] = university_structure

university1_next = {
    "other": {
        "template_sid": "HX335f8a75bf2defe3d84115530b131d08",
        "next": university2_next
    },
}
for university1 in ["wua","cuz", "rcu", "zegu", "au", "su","zils", "msuas", "gsu", "buse"]:
    university1_next[university1] = university_structure

university_next = {
    "other": {
        "template_sid": "HX1a6cf9b1a0151fb3d65beac3f996bb5c",
        "next": university1_next
    },
}
for university in ["uz","nust", "msu", "cut", "buse", "gzu","lsu", "hit", "zou"]:
    university_next[university] = university_structure


conversation_tree = {
    "hi": {
        "template_sid": [
            "HXe398fbeeb1527f117dacdf81ef55872a",
        ],
        "next": {
            "I'm interested": {
                "template_sid": "HX0017bae87caaa68eac896c1ae0d208ab",
                "next": {
                    "olevel": {
                        "template_sid": "HXe35c764d7192f464429a45ccc468225a",
                        "next": {
                            "Back": {
                                "template_sid": "HX0017bae87caaa68eac896c1ae0d208ab",
                            },
                        },
                    },
                    "alevel": {
                        "template_sid": "HXe35c764d7192f464429a45ccc468225a",
                        "next": {
                            "Back": {
                                "template_sid": "HX0017bae87caaa68eac896c1ae0d208ab",
                            },
                        },
                    },
                    "highschoolgraduate": {
                        "template_sid": "HX6f69774bfea92f7321971f43e30aaaac",
                        "next": {
                            "View more details": {
                                "template_sid": "HXb766871877d2ce2508ef18a1176549ed",
                                "next":{
                                    "careerguidance": {
                                        "template_sid": [ "HX4a32bab4533feddab1fe17c76426487a",
                                        ],
                                    },
                                    "instinfo": {
                                        "template_sid": ["HX89a6f49f7585f6bdccdf6220ae07878d",
                                        ],
                                    },
                                    "universitylifeguide": {
                                        "template_sid": ["HXa14106300569c8440ff823a291c21fc0",
                                        ],
                                    },
                                    "lifeafteruniversity": {
                                        "template_sid": ["HX11655b3aec779fe85d451f37582d9f72",
                                        ],
                                    },
                                    "ask": {
                                        "template_sid": ["HXd3d3ec36012acd279b24e2c83614c6e4",
                                        ],
                                    },
                                },
                            },
                            "Continue to next": {
                                "template_sid": "HX7e58b8f333a59ced5c8392e1dc064ed8"
                            },
                        },
                    },
                    "universitystudent": {
                        "template_sid": [
                            "HX9dd354784e3d9a9586b2778b92f8d6f8",
                        ],
                        "next": university_next
                    },
                    "polyorcollege": {
                        "template_sid": "HXe35c764d7192f464429a45ccc468225a",
                        "next": {
                            "Back": {
                                "template_sid": "HX0017bae87caaa68eac896c1ae0d208ab",
                            },
                        },
                    },
                },
            },
            "Cancel": {
                "template_sid": "HX6576e856f2085d5abbe43535f53b822d"
            }
        }
    }
}



