<h1 align="center"><p><img src="http://assets.tira.io/tira-icons/tira-logo-32px-white.png" style="vertical-align:bottom"> TIRA Integrated Research Architecture </p></h1>


This repository contains the source code for all the following components of the [TIRA](https://www.tira.io) shared task platform:

- [Host](host): todo
- [Application](application): todo
- [Protocol](protocol): todo

## Setup Your Local Development Environment

First, please clone the repository:
```
git clone git@github.com:tira-io/tira.git
```

Please change your directory to `application`:
```
cd application
```

Install your virtual environment via:
```
make setup
```

Then, to start TIRA locally, please start:

```
make webpack-watch
```

and 

```
make run-develop
```

Then, you can point your browser to the specified URL.

## Resources
* [Wiki](../../wiki): Getting started with TIRA as a developer/administrator
* [User Docs](https://www.tira.io/docs): Getting started with TIRA as a user
* [Papers](https://webis.de/publications.html?q=tira): List of publications
* [Contribution Guide](CONTRIBUTING.md): How to contribute to the TIRA project

## Paper

If you use TIRA in your own research, please be sure to cite our paper

```
@InCollection{potthast:2019c,
  address =             {Berlin Heidelberg New York},
  author =              {Martin Potthast and Tim Gollub and Matti Wiegmann and Benno Stein},
  booktitle =           {{Information Retrieval Evaluation in a Changing World}},
  doi =                 {10.1007/978-3-030-22948-1\_5},
  editor =              {Nicola Ferro and Carol Peters},
  ids =                 {stein:2019r},
  isbn =                {978-3-030-22948-1},
  month =               sep,
  publisher =           {Springer},
  series =              {{The Information Retrieval Series}},
  title =               {{TIRA Integrated Research Architecture}},
  year =                2019
}
```
## License

[MIT License](LICENSE)
