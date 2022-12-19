# AnomalUs3r

## Description
Detection Malicious Behavior using ML.

This work is focused on how malicious actions in code repositories can be classified as anomalies within the developers' behaviours. From the users' actions in the repositories, metrics are calculated and utilized to create behaviour profiles that are then used to detect anomalous behaviours. The proposed solution relies on OneClassSVM (ML model) to assess new commits pushed into the repository and classify them as malicious or not.

The proposed solution comes from the investigation and writing of my master's thesis.

## System Overview

![Alt text](https://github.com/mlpcorreia/anomaluser/blob/master/images/solution-diagram.png?raw=true | width=100)

There is also a implementation of [Anomalicious](https://arxiv.org/abs/2103.03846), used during the investigation to test and compare the accuracy against the proposed solution.


## Disclaimer
The solution present in this repository is a PoC. Using Python in the data phase was not the best decision, and it takes some time with big repositories. In the future, maybe Golang would be a better option.
